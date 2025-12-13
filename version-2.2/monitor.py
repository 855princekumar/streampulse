#!/usr/bin/env python3
"""
Hybrid RTSP + MJPEG Stream Health Monitor — v4.2
• Async worker pools for RTSP & MJPEG (round-robin + exponential backoff)
• RTSP DESCRIBE classification (200/401/403/404/454); MJPEG HTTP 2xx–3xx
• NTP-synced timestamps, adjusted to timezone from config.yaml
• Hot-reloads config.yaml; creates tables for new streams
• Cold-run dependency install (for Alpine/minimal images)
"""

# ---------- Cold-run dependency check ----------
import sys, subprocess
for mod in ["aiohttp", "flask", "pyyaml", "opencv-python-headless", "pytz"]:
    try:
        __import__(mod.split("-")[0])
    except ImportError:
        print(f"[setup] installing {mod}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", mod])

# ---------- Imports ----------
import os, time, yaml, cv2, sqlite3, socket, struct, asyncio, math, pytz
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlparse
import aiohttp
from flask import Flask, jsonify

# --- OPTIONAL: Load MQTT block safely so monitor.py doesn't break ---
def load_config_with_mqtt_support(cfg_path):
    """
    Wrapper to load config.yaml in a backward-compatible way.
    monitor.py only needs timezone, heartbeat_seconds, streams.
    But config may contain an extra 'mqtt:' object which should not break anything.
    """
    import yaml

    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    except Exception as e:
        print(f"[monitor] Failed to load config.yaml: {e}")
        return {
            "heartbeat_seconds": 20,
            "timezone": "UTC",
            "streams": []
        }

    # Ensure required fields exist (protect monitor logic)
    cfg.setdefault("heartbeat_seconds", 20)
    cfg.setdefault("timezone", "UTC")
    cfg.setdefault("streams", [])

    # 'mqtt' block is allowed but not used here
    if "mqtt" not in cfg:
        cfg["mqtt"] = {}  # required for mqtt_service hot reload flow

    return cfg


# ---------- Paths & tunables ----------
BASE = Path(__file__).parent.resolve()
DB_PATH = Path(os.getenv("DB_PATH", BASE / "streams.db"))
CFG_PATH = BASE / "config.yaml"

RTSP_TIMEOUT = float(os.getenv("RTSP_TIMEOUT", "3.5"))
MJPEG_TIMEOUT = float(os.getenv("MJPEG_TIMEOUT", "3.0"))
MAX_WORKERS_PER_TYPE = int(os.getenv("MAX_WORKERS_PER_TYPE", "32"))
BACKOFF_BASE = float(os.getenv("BACKOFF_BASE", "5.0"))  # seconds, grows 2^n
CFG_RELOAD_SEC = 3

# silence OpenCV/FFmpeg noise
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "loglevel;error"
try:
    if hasattr(cv2, "setLogLevel"):
        cv2.setLogLevel(0)
except Exception:
    pass

# ---------- Time (NTP + timezone) ----------
_NTP_DELTA = 2208988800
def ntp_utc_now():
    try:
        addr = ("pool.ntp.org", 123)
        msg = b"\x1b" + 47 * b"\0"
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(2.0)
            s.sendto(msg, addr)
            data, _ = s.recvfrom(48)
        if len(data) == 48:
            sec = struct.unpack("!I", data[40:44])[0] - _NTP_DELTA
            return datetime.fromtimestamp(sec, timezone.utc)
    except Exception:
        pass
    return datetime.now(timezone.utc)

def tz_now(tzname: str) -> str:
    try:
        tz = pytz.timezone(tzname or "UTC")
    except Exception:
        tz = pytz.timezone("UTC")
    return ntp_utc_now().astimezone(tz).isoformat()

# ---------- Config & DB ----------
def read_cfg():
    if not CFG_PATH.exists():
        CFG_PATH.write_text(yaml.safe_dump({"heartbeat_seconds": 10, "timezone": "UTC", "streams": []}, sort_keys=False))
    with open(CFG_PATH, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    cfg.setdefault("heartbeat_seconds", 10)
    cfg.setdefault("timezone", "UTC")
    cfg.setdefault("streams", [])
    return cfg

def tname(name: str) -> str:
    safe = "".join(ch if (ch.isalnum() or ch == "_") else "_" for ch in name.strip())
    if not safe or not (safe[0].isalpha() or safe[0] == "_"):
        safe = f"t_{safe}"
    return f"log_{safe}"

def init_db(cfg):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL;")
    cur.execute("PRAGMA synchronous=NORMAL;")
    cur.execute("CREATE TABLE IF NOT EXISTS streams(name TEXT PRIMARY KEY, url TEXT NOT NULL)")
    cur.execute("CREATE TABLE IF NOT EXISTS users(user TEXT PRIMARY KEY, pass TEXT NOT NULL)")
    if not cur.execute("SELECT 1 FROM users LIMIT 1").fetchone():
        cur.execute("INSERT INTO users VALUES('admin','admin123')")
    for s in cfg["streams"]:
        cur.execute("INSERT OR REPLACE INTO streams(name,url) VALUES(?,?)", (s["name"], s["url"]))
        cur.execute(
            f"""CREATE TABLE IF NOT EXISTS {tname(s["name"])}(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                status TEXT NOT NULL,
                latency_ms INTEGER,
                message TEXT
            )"""
        )
    conn.commit()
    conn.close()

def record(name: str, status: str, latency_ms, message: str, tzname: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        f"INSERT INTO {tname(name)}(ts,status,latency_ms,message) VALUES(?,?,?,?)",
        (tz_now(tzname), status, latency_ms, message),
    )
    conn.commit()
    conn.close()

# ---------- Probes ----------
async def probe_rtsp(url: str):
    t0 = time.monotonic()
    try:
        p = urlparse(url)
        host = p.hostname or "localhost"
        port = p.port or 554
        reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), RTSP_TIMEOUT)
        req = f"DESCRIBE {url} RTSP/1.0\r\nCSeq: 1\r\nUser-Agent: hb/4.2\r\n\r\n"
        writer.write(req.encode("utf-8"))
        await writer.drain()
        data = await asyncio.wait_for(reader.read(512), RTSP_TIMEOUT)
        writer.close()
        try: await writer.wait_closed()
        except Exception: pass
        lat = int((time.monotonic() - t0) * 1000)
        txt = data.decode(errors="ignore")
        if "RTSP/1.0 200" in txt: return True, "RTSP 200", lat
        if "RTSP/1.0 401" in txt: return True, "RTSP 401 Unauthorized", lat
        if "RTSP/1.0 403" in txt: return True, "RTSP 403 Forbidden", lat
        if "RTSP/1.0 404" in txt: return True, "RTSP 404 Not Found", lat
        if "RTSP/1.0 454" in txt: return True, "RTSP 454 Session Not Found", lat
        return False, "RTSP not 200", lat
    except asyncio.TimeoutError:
        return False, "timeout", int((time.monotonic() - t0) * 1000)
    except Exception as e:
        return False, f"error:{e}", int((time.monotonic() - t0) * 1000)

async def probe_http(session: aiohttp.ClientSession, url: str):
    t0 = time.monotonic()
    try:
        # Try HEAD first, then tiny GET
        try:
            async with session.head(url, timeout=MJPEG_TIMEOUT) as r:
                return (200 <= r.status < 400), f"HTTP {r.status}", int((time.monotonic() - t0) * 1000)
        except Exception:
            async with session.get(url, timeout=MJPEG_TIMEOUT) as r:
                _ = await r.content.read(64)
                return (200 <= r.status < 400), f"HTTP {r.status}", int((time.monotonic() - t0) * 1000)
    except asyncio.TimeoutError:
        return False, "timeout", int((time.monotonic() - t0) * 1000)
    except Exception as e:
        return False, f"error:{e}", int((time.monotonic() - t0) * 1000)

def one_frame(url: str):
    t0 = time.time()
    try:
        cap = cv2.VideoCapture(url)
        ok, _ = cap.read()
        cap.release()
        lat = int((time.time() - t0) * 1000)
        return (True, "ok", lat) if ok else (False, "no frame", lat)
    except Exception as e:
        return False, f"cv2err:{e}", int((time.time() - t0) * 1000)

# ---------- Scheduler (worker pools) ----------
class Stream:
    __slots__ = ("name", "url", "is_rtsp", "fails", "backoff_until")
    def __init__(self, name, url):
        self.name = name
        self.url = url
        self.is_rtsp = url.lower().startswith("rtsp://")
        self.fails = 0
        self.backoff_until = 0.0

class Lane:
    def __init__(self, kind):
        self.kind = kind  # "rtsp" or "mjpeg"
        self.items = []
        self.i = 0
        self.lock = asyncio.Lock()
    def set(self, items): self.items, self.i = items, 0
    async def next_rr(self):
        async with self.lock:
            if not self.items: return None
            start = self.i
            now = time.monotonic()
            for _ in range(len(self.items)):
                s = self.items[self.i]
                self.i = (self.i + 1) % len(self.items)
                if now >= s.backoff_until:
                    return s
            return None

class Scheduler:
    def __init__(self):
        self.cfg = load_config_with_mqtt_support(CFG_PATH)
        init_db(self.cfg)
        self.state = {s["name"]: Stream(s["name"], s["url"]) for s in self.cfg["streams"]}
        self.rtsp = Lane("rtsp")
        self.http = Lane("mjpeg")
        self.rebuild()

    def rebuild(self):
        rtsp_items = [v for v in self.state.values() if v.is_rtsp]
        http_items = [v for v in self.state.values() if not v.is_rtsp]
        self.rtsp.set(sorted(rtsp_items, key=lambda x: x.name))
        self.http.set(sorted(http_items, key=lambda x: x.name))

    async def reloader(self):
        while True:
            await asyncio.sleep(CFG_RELOAD_SEC)
            new = read_cfg()
            if yaml.safe_dump(new, sort_keys=True) != yaml.safe_dump(self.cfg, sort_keys=True):
                # sync DB & state
                self.cfg = new
                init_db(self.cfg)
                new_names = set()
                for s in self.cfg["streams"]:
                    new_names.add(s["name"])
                    if s["name"] in self.state:
                        st = self.state[s["name"]]
                        st.url = s["url"]
                        st.is_rtsp = s["url"].lower().startswith("rtsp://")
                    else:
                        self.state[s["name"]] = Stream(s["name"], s["url"])
                # remove missing
                for n in list(self.state.keys()):
                    if n not in new_names:
                        self.state.pop(n, None)
                self.rebuild()

    def workers_and_delay(self, lane: Lane):
        n = len(lane.items)
        H = max(5, int(self.cfg.get("heartbeat_seconds", 10)))
        if n == 0: return 0, 1.0
        target = n / H  # desired checks/sec for this lane
        W = max(1, min(math.ceil(target), MAX_WORKERS_PER_TYPE))
        delay = max(0.05, W / target)
        return W, delay

async def worker_loop(lane: Lane, sched: Scheduler, session: aiohttp.ClientSession, wid: int):
    while True:
        W, delay = sched.workers_and_delay(lane)
        if wid >= W or not lane.items:
            await asyncio.sleep(0.5); continue
        s = await lane.next_rr()
        if not s:
            await asyncio.sleep(0.15); continue
        if time.monotonic() < s.backoff_until:
            await asyncio.sleep(0.05); continue

        if s.is_rtsp:
            ok, msg, lat = await probe_rtsp(s.url)
        else:
            ok, msg, lat = await probe_http(session, s.url)

        if not ok and s.fails >= 3:
            ok2, msg2, lat2 = one_frame(s.url)
            if ok2: ok, msg, lat = ok2, msg2, lat2

        if ok:
            s.fails = 0
            s.backoff_until = 0
            record(s.name, "ok", lat, msg, sched.cfg.get("timezone", "UTC"))
        else:
            s.fails += 1
            back = BACKOFF_BASE * (2 ** min(5, s.fails))
            s.backoff_until = time.monotonic() + min(90.0, back)
            record(s.name, "fail", lat, msg, sched.cfg.get("timezone", "UTC"))

        await asyncio.sleep(delay)

# ---------- Tiny API (for GUI fallback/testing) ----------
app = Flask(__name__)
@app.route("/api/status")
def api_status():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT name FROM streams")
    names = [r[0] for r in cur.fetchall()]
    data = {}
    for n in names:
        tn = tname(n)
        try:
            cur.execute(f"SELECT ts,status,latency_ms,message FROM {tn} ORDER BY id DESC LIMIT 1")
            r = cur.fetchone()
            if r:
                data[n] = {"ts": r[0], "status": r[1], "latency": r[2], "message": r[3]}
            else:
                data[n] = {"ts": "", "status": "", "latency": None, "message": "no data yet"}
        except sqlite3.OperationalError:
            data[n] = {"ts": "", "status": "", "latency": None, "message": "no table"}
    conn.close()
    return jsonify(data)

# ---------- Runner ----------
async def run_monitor():
    sched = Scheduler()
    asyncio.create_task(sched.reloader())
    timeout = aiohttp.ClientTimeout(total=None, connect=3)
    connector = aiohttp.TCPConnector(limit=0, ssl=False)
    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        tasks = []
        for i in range(MAX_WORKERS_PER_TYPE):
            tasks.append(asyncio.create_task(worker_loop(sched.rtsp, sched, session, i)))
            tasks.append(asyncio.create_task(worker_loop(sched.http, sched, session, i)))
        await asyncio.gather(*tasks)

def main():
    import threading
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=7000, debug=False, use_reloader=False),
                     daemon=True).start()
    print("✅ monitor v4.2 running (status API :7000)")
    asyncio.run(run_monitor())

if __name__ == "__main__":
    main()
