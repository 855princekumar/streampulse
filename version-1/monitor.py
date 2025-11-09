#!/usr/bin/env python3
import os, time, yaml, cv2, sqlite3, threading, socket, struct
from datetime import datetime, timezone
from pathlib import Path
from flask import Flask, jsonify

BASE_DIR = Path(__file__).parent.resolve()
DB_PATH = Path(os.getenv("DB_PATH", BASE_DIR / "streams.db"))
CONFIG_PATH = BASE_DIR / "config.yaml"

# quiet the ffmpeg spam
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "loglevel;error"
if hasattr(cv2, "setLogLevel"):
    try: cv2.setLogLevel(0)
    except Exception: pass

# ---------- NTP-backed UTC ----------
_NTP_DELTA = 2208988800
def ntp_utc_now():
    try:
        addr = ("pool.ntp.org", 123)
        msg = b"\x1b" + 47*b"\0"
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(2.0)
            s.sendto(msg, addr)
            data,_ = s.recvfrom(48)
        if len(data)==48:
            seconds = struct.unpack("!I", data[40:44])[0]
            unix_time = seconds - _NTP_DELTA
            return datetime.fromtimestamp(unix_time, timezone.utc)
    except Exception:
        pass
    return datetime.now(timezone.utc)

def utc_iso(): return ntp_utc_now().isoformat()

# ---------- config / db ----------
cfg_lock = threading.Lock()
def read_config():
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(yaml.safe_dump({"heartbeat_seconds":10,"streams":[]}, sort_keys=False), encoding="utf-8")
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        c = yaml.safe_load(f) or {}
    c.setdefault("heartbeat_seconds", 10)
    c.setdefault("streams", [])
    return c

def table_name(name:str)->str:
    safe = "".join(ch if (ch.isalnum() or ch=="_") else "_" for ch in name.strip())
    if not safe or not (safe[0].isalpha() or safe[0]=="_"):
        safe = f"t_{safe}"
    return f"log_{safe}"

def init_db(cfg):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("CREATE TABLE IF NOT EXISTS streams (name TEXT PRIMARY KEY, url TEXT NOT NULL)")
    for s in cfg["streams"]:
        tn = table_name(s["name"])
        conn.execute(f"""CREATE TABLE IF NOT EXISTS {tn}(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            status TEXT NOT NULL,
            latency_ms INTEGER,
            message TEXT)""")
        conn.execute("INSERT OR REPLACE INTO streams (name,url) VALUES (?,?)",(s["name"], s["url"]))
    conn.commit(); conn.close()

def record(name, status, lat, msg):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(f"INSERT INTO {table_name(name)} (ts,status,latency_ms,message) VALUES (?,?,?,?)",
                 (utc_iso(), status, lat, msg))
    conn.commit(); conn.close()

# ---------- stream check ----------
def _grab_one_frame(url):
    try: cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
    except Exception: cap = cv2.VideoCapture(url)
    if not cap.isOpened(): return False, "Cannot open stream", None
    t0 = time.time()
    ok, frame = cap.read()
    lat = int((time.time()-t0)*1000)
    cap.release()
    if ok and frame is not None: return True,"ok",lat
    return False,"No frame",lat

def check_stream(url, timeout=4):
    result = {"ok":False, "msg":"timeout", "lat":None}
    def worker():
        try:
            ok,msg,lat = _grab_one_frame(url)
            result.update(ok=ok,msg=msg,lat=lat)
        except Exception as e:
            result.update(ok=False,msg=f"error: {e}",lat=None)
    t = threading.Thread(target=worker, daemon=True)
    t.start(); t.join(timeout)
    if t.is_alive(): return False,"timeout",None
    return result["ok"], result["msg"], result["lat"]

def is_rtsp(url:str)->bool:
    return url.lower().startswith("rtsp://")
def is_mjpeg(url:str)->bool:
    u = url.lower()
    return u.startswith("http://") or u.startswith("https://")

# ---------- round-robin workers (2 lanes) ----------
stop_event = threading.Event()

class Lane:
    def __init__(self, lane_type:str):
        self.lane_type = lane_type  # "rtsp" or "mjpeg"
        self.streams = []           # [{'name','url'}, ...]
        self.idx = 0                # round-robin index

    def refresh(self, all_streams):
        if self.lane_type=="rtsp":
            self.streams = [s for s in all_streams if is_rtsp(s["url"])]
        else:
            self.streams = [s for s in all_streams if is_mjpeg(s["url"])]
        if self.idx >= len(self.streams): self.idx = 0

    def next_stream(self):
        if not self.streams: return None
        s = self.streams[self.idx]
        self.idx = (self.idx + 1) % len(self.streams)
        return s

def pacing(total_streams:int, heartbeat:int)->float:
    # aim: full cycle ≈ max(heartbeat, total_streams) seconds
    total_streams = max(1, total_streams)
    full_cycle = max(heartbeat, total_streams)
    return max(0.3, full_cycle / total_streams)  # per-check delay

def lane_worker(lane: Lane, get_cfg_callable):
    last_cfg = None
    while not stop_event.is_set():
        cfg = get_cfg_callable()
        if cfg is not last_cfg:
            # re-init db on config change to ensure tables exist
            init_db(cfg)
            last_cfg = cfg
        lane.refresh(cfg["streams"])

        total = len(cfg["streams"])
        if total == 0 or not lane.streams:
            time.sleep(1); continue

        delay = pacing(total, int(cfg.get("heartbeat_seconds", 10)))

        s = lane.next_stream()
        if s:
            ok,msg,lat = check_stream(s["url"], timeout=4)
            record(s["name"], "ok" if ok else "fail", lat, msg)

        # sleep to keep only one active connection per lane at a time
        slept = 0.0
        while slept < delay and not stop_event.is_set():
            time.sleep(0.1); slept += 0.1

# shared cfg accessor
_current_cfg = read_config()
_cfg_lock = threading.Lock()
def get_cfg():
    global _current_cfg
    with _cfg_lock:
        # refresh from disk every second
        _current_cfg = read_config()
        return _current_cfg

# ---------- optional status API ----------
app = Flask(__name__)
@app.route("/api/status")
def api_status():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT name FROM streams"); names = [r[0] for r in cur.fetchall()]
    data = {}
    for n in names:
        tn = table_name(n)
        try:
            cur.execute(f"SELECT ts,status,latency_ms,message FROM {tn} ORDER BY id DESC LIMIT 1")
            row = cur.fetchone()
            if row:
                data[n] = {"ts": row[0], "status": row[1], "latency": row[2], "message": row[3]}
        except sqlite3.OperationalError:
            pass
    conn.close()
    return jsonify(data)

def main():
    cfg = read_config(); init_db(cfg)
    rtsp_lane = Lane("rtsp")
    mjpeg_lane = Lane("mjpeg")
    threading.Thread(target=lane_worker, args=(rtsp_lane, get_cfg), daemon=True).start()
    threading.Thread(target=lane_worker, args=(mjpeg_lane, get_cfg), daemon=True).start()
    print("✅ Monitor running (round-robin; 1 RTSP + 1 MJPEG at a time) — /api/status on :7000")
    app.run(host="0.0.0.0", port=7000, debug=False)

if __name__ == "__main__":
    main()
