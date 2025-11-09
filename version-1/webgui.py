#!/usr/bin/env python3
import sqlite3
import yaml
import cv2
import time
import io
import csv
from pathlib import Path
from flask import (
    Flask, render_template_string, request, redirect, url_for,
    jsonify, flash, session, Response
)
import os

# ---------------------------------------------------------------------
BASE_DIR = Path(__file__).parent.resolve()
DB_PATH = Path(os.getenv("DB_PATH", BASE_DIR / "streams.db"))
CONFIG_PATH = BASE_DIR / "config.yaml"

app = Flask(__name__)
app.secret_key = "stream_gui_secret"

# =================== UTILS ===================
def table_name(name: str) -> str:
    safe = "".join(c if (c.isalnum() or c == "_") else "_" for c in name.strip())
    if not safe or not (safe[0].isalpha() or safe[0] == "_"):
        safe = f"t_{safe}"
    return f"log_{safe}"

def read_config():
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(
            yaml.safe_dump({"heartbeat_seconds": 10, "streams": []}, sort_keys=False),
            encoding="utf-8",
        )
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {"heartbeat_seconds": 10, "streams": []}

def write_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, sort_keys=False)

def get_uptime(name, last_n=1000):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    tn = table_name(name)
    try:
        cur.execute(f"SELECT status FROM {tn} ORDER BY id DESC LIMIT ?", (last_n,))
        rows = cur.fetchall()
    except sqlite3.OperationalError:
        rows = []
    conn.close()
    if not rows:
        return None
    total = len(rows)
    oks = sum(1 for r in rows if r[0] == "ok")
    return round(100.0 * oks / total, 2)

def latest_row(name):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    tn = table_name(name)
    try:
        cur.execute(f"SELECT ts, status, latency_ms, message FROM {tn} ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
    except sqlite3.OperationalError:
        row = None
    conn.close()
    if not row:
        return None
    return {"ts": row[0], "status": row[1], "latency": row[2], "message": row[3]}

def history_rows(name, limit=200):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    tn = table_name(name)
    try:
        cur.execute(f"SELECT ts, status, latency_ms, message FROM {tn} ORDER BY id DESC LIMIT ?", (limit,))
        rows = cur.fetchall()
    except sqlite3.OperationalError:
        rows = []
    conn.close()
    return [{"ts": r[0], "status": r[1], "latency": r[2], "message": r[3]} for r in rows]

# =================== SETTINGS (TIMEZONE + AUTH) ===================
def init_settings():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    cur.execute("INSERT OR IGNORE INTO app_settings (key, value) VALUES ('timezone', '')")
    conn.commit()
    conn.close()

def get_timezone():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT value FROM app_settings WHERE key='timezone'")
    row = cur.fetchone()
    conn.close()
    return (row[0] if row else "") or ""

def set_timezone(tz: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('timezone', ?)", (tz,))
    conn.commit()
    conn.close()

def init_auth():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS admin_auth (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL
        )
    """)
    cur.execute("SELECT COUNT(*) FROM admin_auth")
    count = cur.fetchone()[0]
    if count == 0:
        cur.execute("INSERT INTO admin_auth (username, password) VALUES (?,?)", ("admin", "admin123"))
        conn.commit()
    conn.close()

def get_admin_creds():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT username, password FROM admin_auth LIMIT 1")
    row = cur.fetchone()
    conn.close()
    if row:
        return {"username": row[0], "password": row[1]}
    return {"username": "admin", "password": "admin123"}

def update_admin_password(new_password):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE admin_auth SET password=? WHERE username='admin'", (new_password,))
    conn.commit()
    conn.close()

init_auth()
init_settings()

# =================== API ROUTES ===================
@app.route("/api/summary")
def api_summary():
    cfg = read_config()
    tz = get_timezone()
    data = []
    for s in cfg["streams"]:
        last = latest_row(s["name"])
        uptime = get_uptime(s["name"], last_n=1000)
        data.append({
            "name": s["name"],
            "url": s["url"],
            "last": last,
            "uptime": uptime
        })
    return jsonify({"heartbeat_seconds": cfg.get("heartbeat_seconds", 10), "streams": data, "timezone": tz})

@app.route("/api/history/<name>")
def api_history(name):
    return jsonify({"name": name, "records": history_rows(name, limit=400)})

@app.route("/api/set-timezone", methods=["POST"])
def api_set_timezone():
    tz = (request.form.get("timezone") or "").strip()
    set_timezone(tz)
    return jsonify({"ok": True, "timezone": tz})

# Export all logs as CSV
@app.route("/export/all.csv")
def export_all():
    cfg = read_config()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["stream","ts_utc","status","latency_ms","message"])
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    for s in cfg["streams"]:
        tn = table_name(s["name"])
        try:
            cur.execute(f"SELECT ts,status,latency_ms,message FROM {tn} ORDER BY id ASC")
            for ts,status,lat,msg in cur.fetchall():
                writer.writerow([s["name"], ts, status, lat, (msg or "").replace("\n"," ")])
        except sqlite3.OperationalError:
            continue
    conn.close()
    data = output.getvalue().encode("utf-8")
    return Response(
        data,
        headers={
            "Content-Type": "text/csv; charset=utf-8",
            "Content-Disposition": 'attachment; filename="all_stream_logs.csv"'
        }
    )

# =================== PREVIEW STREAM ===================
def open_url_for_name(name):
    cfg = read_config()
    for s in cfg["streams"]:
        if s["name"] == name:
            return s["url"]
    return None

@app.route("/preview/<name>")
def preview(name):
    url = open_url_for_name(name)
    if not url:
        return "Unknown stream", 404
    def gen():
        try:
            cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        except Exception:
            cap = cv2.VideoCapture(url)
        if not cap.isOpened():
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n\r\n"
            return
        start = time.time()
        while time.time() - start < 5.0:
            ok, frame = cap.read()
            if not ok or frame is None:
                time.sleep(0.05)
                continue
            ok2, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
            if not ok2:
                continue
            jpg = buf.tobytes()
            yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpg + b"\r\n")
        cap.release()
    return Response(gen(), mimetype="multipart/x-mixed-replace; boundary=frame")

# =================== HTML THEMES / UI ===================
BASE_CSS = """
.mono{font-family:ui-monospace,Menlo,Monaco,Consolas,"Courier New",monospace;}
.chip{padding:.15rem .5rem;border-radius:999px;font-size:.8rem;background:#eee}
.ok-badge{background:#e6f4ea;color:#0b5f2e}
.fail-badge{background:#fde7e7;color:#a50e0e}
.uptime-chip{background:#dbe6ff;color:#0b2a78}
.wrap{word-break:break-all}
.muted{opacity:.8}
.clickable{cursor:pointer;text-decoration:underline}
#themeToggle{margin-left:.5rem}
"""

# =================== DASHBOARD HTML ===================
DASH_HTML = """<!doctype html>
<html data-theme="light">
<head>
<meta charset="utf-8"/><title>Stream Heartbeats</title>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<link href="https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css" rel="stylesheet">
<style>{{ base_css }}</style>
</head><body><main class="container">
<nav>
<ul><li><strong>Stream Heartbeats</strong></li></ul>
<ul>
<li><a href="{{ url_for('settings') }}">Settings</a></li>
<li><a href="{{ url_for('export_all') }}">Export CSV</a></li>
<li class="muted">Theme <input type="checkbox" id="themeToggle"></li>
</ul>
</nav>
<article class="muted">Timezone: <span id="tzDisplay">—</span> <button id="useBrowserTz" class="secondary">Use Browser TZ</button></article>
<article id="loading" class="muted">Loading…</article>
<table id="grid" role="grid" style="display:none">
<thead><tr><th>Status</th><th>Name/URL</th><th>Uptime</th><th>Last</th><th>Latency</th><th>Msg</th><th>History</th><th>Preview</th></tr></thead>
<tbody id="rows"></tbody>
</table>
<p class="muted">Auto-refresh every <span id="hb">—</span>s</p>
<dialog id="histdlg"><article><header><strong id="histTitle">History</strong></header>
<table role="grid"><thead><tr><th>TS</th><th>Status</th><th>Lat</th><th>Msg</th></tr></thead><tbody id="histRows"></tbody></table>
<footer><button onclick="document.getElementById('histdlg').close()">Close</button></footer></article></dialog>
</main>
<script>
// theme toggle
const t=localStorage.getItem('hb_theme')||'light';document.documentElement.setAttribute('data-theme',t);
document.getElementById('themeToggle').checked=(t==='dark');
document.getElementById('themeToggle').addEventListener('change',()=>{const c=document.documentElement.getAttribute('data-theme');const n=(c==='dark')?'light':'dark';document.documentElement.setAttribute('data-theme',n);localStorage.setItem('hb_theme',n);});

// timezone logic
let serverTZ='';
function browserTZ(){try{return Intl.DateTimeFormat().resolvedOptions().timeZone;}catch(e){return 'UTC';}}
function fmtTsUTCtoTZ(iso,tz){try{const dt=new Date(iso);return dt.toLocaleString(undefined,{timeZone:tz,hour12:false})}catch(e){return iso;}}
async function fetchSummary(){return await (await fetch('/api/summary',{cache:'no-store'})).json();}
async function fetchHistory(n){return await (await fetch('/api/history/'+encodeURIComponent(n),{cache:'no-store'})).json();}
function esc(s){return s==null?'':String(s).replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));}
function badge(l){if(!l)return'<span class="chip fail-badge">Not Healthy</span>';return l.status==='ok'?'<span class="chip ok-badge">Healthy</span>':'<span class="chip fail-badge">Not Healthy</span>';}
async function setServerTZ(tz){const fd=new FormData();fd.append('timezone',tz);await fetch('/api/set-timezone',{method:'POST',body:fd});}
document.getElementById('useBrowserTz').addEventListener('click',async()=>{const tz=browserTZ();await setServerTZ(tz);serverTZ=tz;document.getElementById('tzDisplay').textContent=tz;render();});
async function render(){const d=await fetchSummary();serverTZ=d.timezone||'';if(!serverTZ){const tz=browserTZ();await setServerTZ(tz);serverTZ=tz;}document.getElementById('tzDisplay').textContent=serverTZ;document.getElementById('hb').textContent=d.heartbeat_seconds||'—';const r=document.getElementById('rows');r.innerHTML='';(d.streams||[]).forEach(s=>{const l=s.last;const tsLocal=l?fmtTsUTCtoTZ(l.ts,serverTZ):'—';const tr=document.createElement('tr');tr.innerHTML=`<td>${badge(l)}</td><td><b>${esc(s.name)}</b><br><span class="mono">${esc(s.url)}</span></td><td>${s.uptime!=null?'<span class="chip uptime-chip">'+s.uptime+'%</span>':'—'}</td><td class="mono">${esc(tsLocal)}</td><td>${l&&l.latency!=null?l.latency+'ms':'—'}</td><td class="mono">${l?esc(l.message):'—'}</td><td><span class="clickable" onclick="hist('${encodeURIComponent(s.name)}')">view</span></td><td><a href="/preview/${encodeURIComponent(s.name)}" target="_blank">open</a></td>`;r.appendChild(tr);});document.getElementById('loading').style.display='none';document.getElementById('grid').style.display='';}
async function hist(n){const d=await fetchHistory(decodeURIComponent(n));const tb=document.getElementById('histRows');tb.innerHTML='';(d.records||[]).forEach(r=>{const tsLocal=fmtTsUTCtoTZ(r.ts,serverTZ);tb.innerHTML+=`<tr><td>${esc(tsLocal)}</td><td>${r.status==='ok'?'<span class="chip ok-badge">ok</span>':'<span class="chip fail-badge">fail</span>'}</td><td>${r.latency||'—'}</td><td class="mono">${esc(r.message||'')}</td></tr>`;});document.getElementById('histTitle').textContent='History - '+decodeURIComponent(n);document.getElementById('histdlg').showModal();}
render();setInterval(render,5000);
</script></body></html>"""

# =================== LOGIN ===================
LOGIN_HTML = """<!doctype html>
<html data-theme="light"><head><meta charset="utf-8"/><title>Login</title>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<link href="https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css" rel="stylesheet">
<style>{{ base_css }}</style></head>
<body><main class="container">
<article><h3>Admin Login</h3>
{% with messages = get_flashed_messages() %}
{% if messages %}<article>{% for m in messages %}<p>{{ m }}</p>{% endfor %}</article>{% endif %}{% endwith %}
<form method="post">
<label>Username<input name="username" required></label>
<label>Password<input name="password" type="password" required></label>
<button type="submit">Login</button></form>
<footer><p class="muted">Default: admin / admin123</p>
<a href="{{ url_for('dashboard') }}" role="button" class="secondary">← Back to Dashboard</a></footer>
</article></main></body></html>"""

# =================== SETTINGS ===================
SETTINGS_HTML = """<!doctype html>
<html data-theme="light"><head><meta charset="utf-8"/><title>Settings</title>
<link href="https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css" rel="stylesheet">
<style>{{ base_css }}</style></head>
<body><main class="container">
<nav><ul><li><strong>Settings</strong></li></ul>
<ul><li><a href="{{ url_for('dashboard') }}">Back</a></li><li><a href="{{ url_for('logout') }}">Logout</a></li><li class="muted">Theme <input type="checkbox" id="themeToggle"></li></ul></nav>
{% with messages = get_flashed_messages() %}
{% if messages %}<article>{% for m in messages %}<p>{{ m }}</p>{% endfor %}</article>{% endif %}{% endwith %}
<form method="post">
<label>Heartbeat <input name="hb" type="number" min="2" max="3600" value="{{ cfg.get('heartbeat_seconds',10) }}"></label>
<fieldset><legend>Timezone</legend>
<p class="muted">Auto-detected from your browser on first load. You can override it here.</p>
<label>Current timezone<input id="tzInput" name="tz" value="{{ current_tz or '' }}" placeholder="e.g. Asia/Kolkata"></label>
<button type="button" id="setBrowserTz">Use Browser Timezone</button></fieldset>
{% for s in cfg.streams %}
<article><label>Name<input name="name_{{ loop.index0 }}" value="{{ s.name }}"></label>
<label>URL<input name="url_{{ loop.index0 }}" value="{{ s.url }}"></label>
<label><input type="checkbox" name="del_{{ loop.index0 }}">Delete</label></article>
{% endfor %}
<details><summary>Add new stream</summary>
<article><label>Name<input name="new_name"></label><label>URL<input name="new_url"></label></article></details>
<label>New Password<input name="new_password" type="password" placeholder="leave blank to keep"></label>
<button>Save</button></form>
</main>
<script>
const t=localStorage.getItem('hb_theme')||'light';document.documentElement.setAttribute('data-theme',t);
document.getElementById('themeToggle').checked=(t==='dark');
document.getElementById('themeToggle').addEventListener('change',()=>{const c=document.documentElement.getAttribute('data-theme');const n=(c==='dark')?'light':'dark';document.documentElement.setAttribute('data-theme',n);localStorage.setItem('hb_theme',n);});
document.getElementById('setBrowserTz').addEventListener('click',()=>{try{document.getElementById('tzInput').value=Intl.DateTimeFormat().resolvedOptions().timeZone;}catch(e){document.getElementById('tzInput').value='UTC';}});
</script></body></html>"""

# =================== ROUTES ===================
@app.route("/")
def dashboard(): return render_template_string(DASH_HTML, base_css=BASE_CSS)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        creds = get_admin_creds()
        if request.form.get("username") == creds["username"] and request.form.get("password") == creds["password"]:
            session["is_admin"] = True
            return redirect(url_for("settings"))
        flash("Invalid credentials.")
    return render_template_string(LOGIN_HTML, base_css=BASE_CSS)

@app.route("/logout")
def logout():
    session.clear(); flash("Logged out."); return redirect(url_for("dashboard"))

@app.route("/settings", methods=["GET", "POST"])
def settings():
    if not session.get("is_admin"): return redirect(url_for("login"))
    cfg = read_config()
    current_streams = [s["name"] for s in cfg.get("streams", [])]
    current_tz = get_timezone()
    if request.method == "POST":
        hb = int(request.form.get("hb", 10)); hb = max(2, min(3600, hb))
        updated, removed = [], []
        for i, s in enumerate(cfg.get("streams", [])):
            if request.form.get(f"del_{i}"):
                removed.append(s["name"]); continue
            name = (request.form.get(f"name_{i}") or "").strip()
            url  = (request.form.get(f"url_{i}")  or "").strip()
            if name and url: updated.append({"name": name, "url": url})
        new_name = (request.form.get("new_name") or "").strip()
        new_url  = (request.form.get("new_url")  or "").strip()
        if new_name and new_url: updated.append({"name": new_name, "url": new_url})
        old_set, new_set = set(current_streams), set([s["name"] for s in updated])
        removed += list(old_set - new_set)
        cfg["heartbeat_seconds"] = hb; cfg["streams"] = updated; write_config(cfg)
        if removed:
            conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
            for name in removed:
                tn = table_name(name)
                try: cur.execute(f"DROP TABLE IF EXISTS {tn}")
                except sqlite3.OperationalError: pass
            conn.commit(); conn.close()
        tz = (request.form.get("tz") or "").strip()
        if tz != current_tz: set_timezone(tz); current_tz = tz; flash(f"Timezone set to {tz or 'auto'}")
        new_pw = (request.form.get("new_password") or "").strip()
        if new_pw: update_admin_password(new_pw); flash("Password updated.")
        flash("Settings saved. Removed streams purged from DB.")
        return redirect(url_for("settings"))
    return render_template_string(SETTINGS_HTML, base_css=BASE_CSS, cfg=cfg, current_tz=current_tz)

if __name__ == "__main__":
    print("🌐 Web GUI running on :8000 — dynamic export, timezone, DB-safe")
    app.run(host="0.0.0.0", port=8000, debug=False)
