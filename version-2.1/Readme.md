#  StreamPulse v2.1  
A lightweight RTSP/HTTP stream heartbeat monitoring dashboard with live status, logging, preview, auto-refresh, and persistent storage via Docker.

---

##  What’s New in Version 2.1

Version **2.1** is a major improvement over the older **v2.0** release.  
The entire system was re-architected to make it **production-ready**, **persistent**, and **fully Dockerized**.

###  Key Updates

#### 1. **Full Docker Migration**
- Added a complete Dockerfile optimized for Python 3.11-slim  
- Clean separation of:
  - App files `/app/`
  - Default config/database `/defaults/`
  - Host persistent storage `/host/`
- Supports Linux, Windows, macOS (Docker Desktop)

#### 2. **Supervisor-based Process Management**
- Introduced `supervisord` to run:
  - `monitor.py` (backend heartbeat)
  - `webgui.py` (frontend Flask GUI)
- Auto-restart on crash  
- Clean logs (`stdout_logfile=NONE`)

#### 3. **Persistent Config & Database (Live Sync)**
- Config (`config.yaml`) and DB (`streams.db`) now stored **outside** container
- Auto-initialization:
  - If host config/DB missing → copy defaults from image
- Live sync:
  - Editing host file updates running container instantly  
  - Editing container file updates host instantly  

#### 4. **Symlink Architecture**
To avoid file mount issues (especially on Windows), the container now uses:

```
/app/config.yaml   -> symlink to /host/config.yaml  
/app/streams.db    -> symlink to /host/streams.db
```

This guarantees:
- Zero mount path errors  
- Real-time sync  
- Full cross-OS compatibility  

#### 5. **Improved Database Initialization**
- Auto-creation of log tables (`log_<stream>`) on startup
- Monitor and GUI stay fully in sync
- Fixed “no table” issues and race conditions

#### 6. **Port Mapping Fix**
- Internal ports:
  - API → **7000**
  - GUI → **8000**
- Host ports:
  - API → **6868**
  - GUI → **6969**

---

##  Folder Structure (Persistent Storage)

When running Docker Compose, the following folder is created:

```
StreamPulse-v2.1/
 ├── config.yaml   # Persistent configuration
 └── streams.db    # Persistent SQLite logs
```

These files survive container restarts, updates, and rebuilds.

---

## 🐳 Docker Compose (Production Ready)

```yaml
services:
  streampulse:
    image: devprincekumar/streampulse:2.1
    container_name: StreamPulse-v2.1
    restart: unless-stopped

    ports:
      - "6868:7000"   # Monitor API
      - "6969:8000"   # Web GUI

    volumes:
      - ./StreamPulse-v2.1:/host
```

Run with:

```
docker compose up -d
```

GUI available at:

```
http://localhost:6969
```

Monitor API:

```
http://localhost:6868/api/status
```

---

##  Technical Architecture

### 1. **monitor.py**
- Periodically checks each stream (RTSP/HTTP)
- Stores latency, status, message, timestamp into SQLite log tables
- Reloads config every few seconds
- Auto-creates missing log tables

### 2. **webgui.py**
- User-friendly dashboard
- Live status, preview button, history
- Settings panel updates config.yaml
- Syncs DB with config

### 3. **supervisord**
Runs both processes with stability:

- Auto-restart  
- No output buffering  
- No crashes on heavy logs  

### 4. **entrypoint.sh**
- Ensures config/db exist on host  
- Copies defaults if missing  
- Creates symlinks into `/app/`  
- Starts supervisor  

---

##  The Journey from v2.0 → v2.1 (Story)

This release wasn’t just a version bump — it was a complete transformation.  
Here’s the journey:

###  **1. Starting Point**
- v2.0 was functional but not Docker friendly.
- Config & DB stayed inside the container.
- Restarting the container reset everything.
- monitor.py and webgui.py had had to be run manually.

###  **2. First Challenge — Persistent Storage**
- Docker bind mounts initially failed.
- config.yaml sometimes became a *folder* inside container.
- Windows/WSL paths caused “Mount file vs directory” errors.

###  **The Solution**
- Move defaults to `/defaults`
- Mount host folder to `/host`
- Create symlinks `/app/config.yaml` → `/host/config.yaml`

This eliminated all mount conflicts.

###  **3. Second Challenge — Dual Process Management**
Running both scripts via:

```
python monitor.py & python webgui.py
```

was unreliable.

###  **The Solution**
Use `supervisord` — stable, restartable, clean.

###  **4. Third Challenge — “no table” issue**
GUI showed:

```
no table
```

because DB had no log tables.

###  **The Solution**
- Ensure DB resets properly on missing state
- Let monitor create tables immediately on startup
- Compose down → up fixed race condition
- DB now initializes correctly on first start

###  **5. Fourth Challenge — Illegal seek**
Supervisor log rotation error:

```
OSError: [Errno 29] Illegal seek
```

###  **The Solution**
Use:

```
stdout_logfile=NONE
stderr_logfile=NONE
```

No logging crashes anymore.

---

##  Final Result

With all improvements:

- ✔ Fully Dockerized  
- ✔ Persistent & stable  
- ✔ Live-sync config/db  
- ✔ Cross-platform  
- ✔ No more table errors  
- ✔ No more mount failures  
- ✔ No more process crashes  
- ✔ Clean, reliable monitoring dashboard  

StreamPulse v2.1 is now production-ready.

---

##  Local Development (without Docker)

```bash
pip install -r requirements.txt
python monitor.py
python webgui.py
```

---

##  GitHub Repository Structure

```
/
├── monitor.py
├── webgui.py
├── config.yaml
├── streams.db
├── supervisord.conf
├── entrypoint.sh
├── Dockerfile
└── docker-compose.yml
```


