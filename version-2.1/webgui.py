#!/usr/bin/env python3
"""
Web GUI for Hybrid Monitor — v4.2
• Login (admin/admin123 default; changeable)
• Browser timezone auto-detect + confirm (stores in config.yaml); dropdown override
• Dashboard: legend, history modal (top-right close), 5s live preview, Export CSV button
• Responsive dark UI; URLs hidden on dashboard (privacy); shows RTSP/MJPEG label
• On Save: writes config, syncs DB tables, redirects to dashboard (streams appear instantly)
• Cold-run dependency install
"""
# ---------- Cold-run deps ----------
import sys, subprocess
for mod in ["flask", "pyyaml", "pytz", "tzlocal", "opencv-python-headless"]:
    try: __import__(mod.split("-")[0])
    except ImportError:
        print(f"[setup] installing {mod}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", mod])

# ---------- Imports ----------
from flask import Flask, render_template_string, request, redirect, url_for, session, Response, jsonify
import os, yaml, sqlite3, csv, io, threading, cv2, time, pytz
from tzlocal import get_localzone_name
from pathlib import Path

BASE = Path(__file__).parent.resolve()
DB_PATH = Path(os.getenv("DB_PATH", BASE / "streams.db"))
CFG_PATH = BASE / "config.yaml"

app = Flask(__name__)
app.secret_key = "stream_gui_secret"

# ---------- Helpers ----------
def tname(name: str) -> str:
    safe = "".join(ch if (ch.isalnum() or ch == "_") else "_" for ch in name.strip())
    if not safe or not (safe[0].isalpha() or safe[0] == "_"):
        safe = f"t_{safe}"
    return f"log_{safe}"

def read_cfg():
    if not CFG_PATH.exists():
        CFG_PATH.write_text(yaml.safe_dump({"heartbeat_seconds": 10, "timezone": "UTC", "streams": []}, sort_keys=False))
    with open(CFG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {"heartbeat_seconds": 10, "timezone": "UTC", "streams": []}

def write_cfg(cfg):
    with open(CFG_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, sort_keys=False)

def ensure_db_user_default():
    conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS users(user TEXT PRIMARY KEY, pass TEXT NOT NULL)")
    if not cur.execute("SELECT 1 FROM users LIMIT 1").fetchone():
        cur.execute("INSERT INTO users VALUES('admin','admin123')")
    conn.commit(); conn.close()

def streams_sync_db(streams):
    """Ensure streams table & per-stream log tables match config immediately (for instant dashboard reflect)."""
    conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS streams(name TEXT PRIMARY KEY, url TEXT NOT NULL)")
    existing = {r[0] for r in cur.execute("SELECT name FROM streams")}
    incoming = {s["name"] for s in streams}
    # delete removed
    for name in (existing - incoming):
        cur.execute("DELETE FROM streams WHERE name=?", (name,))
        try: cur.execute(f"DROP TABLE IF EXISTS {tname(name)}")
        except sqlite3.OperationalError: pass
    # upsert current
    for s in streams:
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
    conn.commit(); conn.close()

def check_login(user, pw):
    conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS users(user TEXT PRIMARY KEY, pass TEXT NOT NULL)")
    cur.execute("SELECT pass FROM users WHERE user=?", (user,))
    row = cur.fetchone(); conn.close()
    return bool(row and row[0] == pw)

def set_password(user, newpw):
    conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO users(user,pass) VALUES(?,?)", (user, newpw))
    conn.commit(); conn.close()

def latest_all():
    """Return status for all streams, including those with no rows yet."""
    cfg = read_cfg()
    names = [s["name"] for s in cfg.get("streams", [])]
    conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
    data = {}
    for n in names:
        try:
            cur.execute(f"SELECT ts,status,latency_ms,message FROM {tname(n)} ORDER BY id DESC LIMIT 1")
            r = cur.fetchone()
            if r: data[n] = {"ts": r[0], "status": r[1], "latency": r[2], "message": r[3]}
            else: data[n] = {"ts": "", "status": "", "latency": None, "message": "no data yet"}
        except sqlite3.OperationalError:
            data[n] = {"ts": "", "status": "", "latency": None, "message": "no table"}
    conn.close()
    return data

# ---------- Templates ----------
LOGIN_HTML = r"""
<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Login</title><style>
body{font-family:Segoe UI,system-ui;background:#0b0b0c;color:#eee;margin:0;display:grid;place-items:center;height:100vh}
.card{background:#12141a;border-radius:12px;padding:20px;width:min(320px,92%)}
input{width:100%;padding:10px;border-radius:8px;border:1px solid #2a2f3f;background:#0f1117;color:#e9eaee;margin:6px 0}
button{width:100%;padding:10px;border:0;border-radius:8px;background:#1f2330;color:#fff;cursor:pointer}
.small{opacity:.8;font-size:.9rem}
</style></head><body>
<div class="card">
<h3>🔐 Admin Login</h3>
<form method="post">
<input name="user" placeholder="Username" required>
<input name="pw" type="password" placeholder="Password" required>
<button>Login</button>
<p class="small">Default: admin / admin123</p>
</form>
</div></body></html>
"""

DASH_HTML = r"""
<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Stream Dashboard</title>
<style>
body{font-family:system-ui,Segoe UI;background:#0b0b0c;color:#e9eaee;margin:0}
main{max-width:1200px;margin:auto;padding:1rem}
nav{display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem;gap:.5rem;flex-wrap:wrap}
button,a.btn{background:#1f2330;color:#fff;border:0;border-radius:8px;padding:8px 12px;cursor:pointer;text-decoration:none}
.badge{padding:2px 8px;border-radius:999px;font-size:.85rem}
.green{background:#13381a;color:#5dffa1}
.red{background:#391717;color:#ff7d7d}
.yellow{background:#3a3413;color:#ffe07a}
.type{padding:2px 8px;border:1px solid #2a2f3f;border-radius:999px;font-size:.75rem;color:#bfc4d6}
table{width:100%;border-collapse:collapse;background:#12141a;border-radius:12px;overflow:hidden}
th,td{padding:10px;border-bottom:1px solid #1e2230;text-align:left}
th{background:#181b25}
.modal{position:fixed;inset:0;background:#000c;display:none;align-items:center;justify-content:center}
.modal .content{background:#12141a;padding:1rem;border-radius:12px;width:min(95%,900px);max-height:90%;overflow:auto}
.small{opacity:.8}
@media(max-width:768px){main{padding:.6rem;font-size:.95rem}}
</style></head><body><main>
<nav>
  <div>
    <strong>📡 Stream Dashboard</strong>
    <span id="tzDisp" class="small"></span>
  </div>
  <div>
    <a class="btn" href="/settings">⚙️ Settings</a>
    <a class="btn" href="/export/all.csv">⬇️ Export CSV</a>
    <button id="legendBtn">ℹ️ Info</button>
    <a class="btn" href="/logout">🚪 Logout</a>
  </div>
</nav>

<div id="legend" class="modal"><div class="content">
  <button style="float:right" onclick="document.getElementById('legend').style.display='none'">❌</button>
  <h3>Status Legend</h3>
  <ul>
    <li>🟢 RTSP 200 / HTTP 200 — Healthy</li>
    <li>🟡 RTSP 401/403/404/454 — Reachable but restricted / path / limit</li>
    <li>🔴 Timeout / No response — Unreachable</li>
  </ul>
</div></div>

<table id="grid">
  <thead><tr><th>Name</th><th>Type</th><th>Status</th><th>Latency</th><th>Message</th><th>Timestamp</th><th>Actions</th></tr></thead>
  <tbody id="rows"><tr><td colspan="7">Loading…</td></tr></tbody>
</table>

<div id="modal" class="modal"><div class="content" id="modalC"></div></div>

<script>
function closeModal(){document.getElementById('modal').style.display='none'}
document.getElementById('legendBtn').onclick=()=>{document.getElementById('legend').style.display='flex'}

async function load(){
  const r=await fetch('/api/status',{cache:'no-store'}); const j=await r.json();
  const rows=[];
  const names=Object.keys(j).sort();
  for(const n of names){
    const v=j[n]||{};
    const typ=(v.message||'').startsWith('HTTP')?'MJPEG':'RTSP';
    let col='green';
    const msg=(v.message||'')+'';
    if(v.status==='fail' || msg.includes('timeout')) col='red';
    else if(/401|403|404|454/.test(msg)) col='yellow';
    rows.push(`<tr>
      <td>${n}</td>
      <td><span class="type">${typ}</span></td>
      <td><span class="badge ${col}">${v.status||''}</span></td>
      <td>${v.latency!=null? v.latency+' ms':''}</td>
      <td>${msg}</td>
      <td>${v.ts||''}</td>
      <td>
        <button onclick="hist('${n}')">History</button>
        <button onclick="prev('${n}')">Preview</button>
      </td>
    </tr>`);
  }
  document.getElementById('rows').innerHTML = rows.join('') || '<tr><td colspan="7">No streams.</td></tr>';
}

async function hist(n){
  const r=await fetch('/history/'+encodeURIComponent(n)); const t=await r.text();
  document.getElementById('modalC').innerHTML=`<button style="float:right" onclick="closeModal()">❌</button><h3>${n} — History (latest 50)</h3><pre style="text-align:left;white-space:pre-wrap">${t}</pre>`;
  document.getElementById('modal').style.display='flex';
}
function prev(n){
  const html = `<button style="float:right" onclick="closeModal()">❌</button>
    <h3>${n} — Live Preview (5s)</h3>
    <img src="/preview/${encodeURIComponent(n)}" style="width:100%;border-radius:8px">`;
  document.getElementById('modalC').innerHTML=html;
  document.getElementById('modal').style.display='flex';
}

async function bootstrapTZ(){
  try{
    const r=await fetch('/api/cfg'); const j=await r.json();
    document.getElementById('tzDisp').textContent = ` • TZ: ${j.timezone} (UTC${j.utc_offset})`;
    if(!j.timezone_set){
      const btz = Intl.DateTimeFormat().resolvedOptions().timeZone;
      if(confirm(`Use your browser timezone "${btz}"?`)){
        const fd=new FormData(); fd.append('tz', btz);
        await fetch('/api/set-tz', {method:'POST', body:fd});
        document.getElementById('tzDisp').textContent = ` • TZ: ${btz} (browser)`;
      }
    }
  }catch(e){}
}

bootstrapTZ();
load(); setInterval(load, 5000);
</script>
</main></body></html>
"""

SETTINGS_HTML = r"""
<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Settings</title>
<style>
body{font-family:system-ui,Segoe UI;background:#0b0b0c;color:#e9eaee;margin:0}
main{max-width:1000px;margin:auto;padding:1rem}
input,select{background:#0f1117;color:#fff;border:1px solid #2a2f3f;border-radius:8px;padding:8px;width:100%}
button,a.btn{background:#1f2330;color:#fff;border:0;border-radius:8px;padding:8px 12px;text-decoration:none;cursor:pointer}
table{width:100%;border-collapse:collapse;background:#12141a;border-radius:12px;overflow:hidden}
th,td{padding:10px;border-bottom:1px solid #1e2230;text-align:left}
th{background:#181b25}
.row{display:flex;gap:10px;flex-wrap:wrap}
.col{flex:1;min-width:240px}
.small{opacity:.8}
@media(max-width:768px){main{padding:.6rem}}
</style></head><body><main>
<div class="row" style="justify-content:space-between;align-items:center">
  <h2>Settings</h2>
  <a class="btn" href="/">⬅ Back</a>
</div>

<form method="post">
  <div class="row">
    <div class="col">
      <label>Heartbeat (seconds)
        <input name="hb" value="{{ cfg.heartbeat_seconds }}">
      </label>
    </div>
    <div class="col">
      <label>Timezone</label>
      <select name="tz" id="tzSel">
        {% for z in tzs %}
          <option value="{{z}}" {% if z==cfg.timezone %}selected{% endif %}>{{z}}</option>
        {% endfor %}
      </select>
      <div class="small">Tip: Click “Use Browser TZ” to auto select your local zone.</div>
      <button type="button" id="useBrowser">Use Browser TZ</button>
    </div>
  </div>

  <h3>Streams</h3>
  <table id="tbl">
    <thead><tr><th>Name</th><th>URL</th><th>Delete</th></tr></thead>
    <tbody>
    {% for s in cfg.streams %}
      <tr>
        <td><input name="name_{{ loop.index0 }}" value="{{ s.name }}"></td>
        <td><input name="url_{{ loop.index0 }}" value="{{ s.url }}"></td>
        <td style="text-align:center"><input type="checkbox" name="del_{{ loop.index0 }}"></td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
  <button type="button" id="add">➕ Add Stream</button>

  <h3>Admin Password</h3>
  <input type="password" name="newpw" placeholder="Leave blank to keep the same">

  <div style="margin-top:10px">
    <button type="submit">💾 Save & Return</button>
  </div>
</form>

<script>
document.getElementById('add').onclick=()=>{
  const tb=document.querySelector('#tbl tbody'); const k=Date.now();
  const tr=document.createElement('tr');
  tr.innerHTML=`<td><input name="new_name_${k}" placeholder="Name"></td>
                <td><input name="new_url_${k}" placeholder="rtsp:// or http(s)://"></td>
                <td></td>`;
  tb.appendChild(tr);
};
document.getElementById('useBrowser').onclick=()=>{
  try{
    const tz=Intl.DateTimeFormat().resolvedOptions().timeZone;
    const sel=document.getElementById('tzSel');
    for(let i=0;i<sel.options.length;i++){ if(sel.options[i].value===tz){ sel.selectedIndex=i; return; } }
    alert("Browser TZ not found in list: "+tz);
  }catch(e){ alert('Browser TZ detect failed'); }
};
</script>
</main></body></html>
"""

# ---------- Routes ----------
@app.route("/login", methods=["GET","POST"])
def login():
    ensure_db_user_default()
    if request.method=="POST":
        if check_login(request.form["user"], request.form["pw"]):
            session["user"] = request.form["user"]
            return redirect("/")
        return render_template_string(LOGIN_HTML)
    return render_template_string(LOGIN_HTML)

@app.route("/logout")
def logout():
    session.clear(); return redirect("/login")

@app.route("/")
def dash():
    if "user" not in session: return redirect("/login")
    return render_template_string(DASH_HTML)

@app.route("/api/cfg")
def api_cfg():
    cfg = read_cfg()
    try:
        tz = pytz.timezone(cfg.get("timezone","UTC"))
        offset = tz.utcoffset(datetime.utcnow().replace(tzinfo=pytz.utc)) or tz.utcoffset(datetime.now())
        sign = "+" if offset.total_seconds()>=0 else "-"
        hh = int(abs(offset.total_seconds())//3600)
        mm = int((abs(offset.total_seconds())%3600)//60)
        off = f"{sign}{hh:02d}:{mm:02d}"
    except Exception:
        off = "+00:00"
    return jsonify({"timezone": cfg.get("timezone","UTC"), "utc_offset": off, "timezone_set": bool(cfg.get("timezone"))})

@app.route("/api/set-tz", methods=["POST"])
def api_set_tz():
    if "user" not in session: return ("", 401)
    tz = (request.form.get("tz") or "UTC").strip()
    try: pytz.timezone(tz)
    except Exception: tz = "UTC"
    cfg = read_cfg(); cfg["timezone"] = tz; write_cfg(cfg)
    return ("ok", 200)

@app.route("/api/status")
def api_status():
    if "user" not in session: return ("", 401)
    return jsonify(latest_all())

@app.route("/history/<name>")
def history(name):
    if "user" not in session: return ("", 401)
    conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
    try:
        cur.execute(f"SELECT ts,status,latency_ms,message FROM {tname(name)} ORDER BY id DESC LIMIT 50")
        rows = cur.fetchall()
    except sqlite3.OperationalError:
        rows = []
    conn.close()
    return "\n".join([f"{ts} | {st} | {lat if lat is not None else ''} ms | {msg}" for ts,st,lat,msg in rows]) or "No history."

@app.route("/preview/<name>")
def preview(name):
    if "user" not in session: return ("", 401)
    conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
    cur.execute("SELECT url FROM streams WHERE name=?", (name,))
    r = cur.fetchone(); conn.close()
    if not r: return "Unknown stream", 404
    url = r[0]
    # 5s MJPEG of frames (non-blocking worker)
    def gen():
        try:
            cap = cv2.VideoCapture(url)
            if not cap.isOpened():
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n\r\n"
                return
            t0 = time.time()
            while time.time() - t0 < 5.0:
                ok, frame = cap.read()
                if not ok or frame is None:
                    time.sleep(0.05); continue
                ok2, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
                if not ok2: continue
                jpg = buf.tobytes()
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpg + b"\r\n"
            cap.release()
        except Exception:
            pass
    return Response(gen(), mimetype="multipart/x-mixed-replace; boundary=frame")

@app.route("/export/all.csv")
def export_all():
    if "user" not in session: return ("", 401)
    cfg = read_cfg()
    out = io.StringIO(); w = csv.writer(out)
    w.writerow(["stream","ts","status","latency_ms","message"])
    conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
    for s in cfg.get("streams", []):
        tn = tname(s["name"])
        try:
            cur.execute(f"SELECT ts,status,latency_ms,message FROM {tn} ORDER BY id ASC")
            for ts,st,lat,msg in cur.fetchall():
                w.writerow([s["name"], ts, st, lat, (msg or "").replace("\n"," ")])
        except sqlite3.OperationalError:
            continue
    conn.close()
    data = out.getvalue().encode("utf-8")
    return Response(data, headers={
        "Content-Type": "text/csv; charset=utf-8",
        "Content-Disposition": 'attachment; filename="stream_logs.csv"'
    })

@app.route("/settings", methods=["GET","POST"])
def settings():
    if "user" not in session: return redirect("/login")
    ensure_db_user_default()
    cfg = read_cfg()
    tzs = pytz.all_timezones
    if request.method == "POST":
        # heartbeat
        try:
            hb = int(float(request.form.get("hb", cfg.get("heartbeat_seconds", 10))))
            hb = max(2, min(3600, hb))
        except Exception:
            hb = cfg.get("heartbeat_seconds", 10)
        cfg["heartbeat_seconds"] = hb
        # timezone
        tz = (request.form.get("tz") or cfg.get("timezone","UTC")).strip()
        try: pytz.timezone(tz)
        except Exception: tz = "UTC"
        cfg["timezone"] = tz
        # streams
        updated = []
        for i, s in enumerate(cfg.get("streams", [])):
            if request.form.get(f"del_{i}"): continue
            nm = (request.form.get(f"name_{i}") or s["name"]).strip()
            ur = (request.form.get(f"url_{i}")  or s["url"]).strip()
            if nm and ur: updated.append({"name": nm, "url": ur})
        for k,v in request.form.items():
            if k.startswith("new_name_"):
                suf = k.split("_",2)[-1]
                nm = (v or "").strip()
                ur = (request.form.get(f"new_url_{suf}") or "").strip()
                if nm and ur: updated.append({"name": nm, "url": ur})
        cfg["streams"] = updated
        write_cfg(cfg)
        # DB sync for instant reflect
        streams_sync_db(updated)
        # password change
        npw = (request.form.get("newpw") or "").strip()
        if npw: set_password("admin", npw)
        return redirect(url_for("dash"))
    return render_template_string(SETTINGS_HTML, cfg=cfg, tzs=tzs)

if __name__ == "__main__":
    print("🌐 WebGUI v4.2 running :8000")
    app.run(host="0.0.0.0", port=8000, debug=False)
