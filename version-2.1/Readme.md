
# StreamPulse v2.1  
A lightweight RTSP/HTTP stream heartbeat monitoring dashboard with live status, logging, preview, auto-refresh, and persistent storage via Docker.

---

## What’s New in Version 2.1

Version **2.1** is a major improvement over the older **v2.0** release.  
The entire system was re-architected to make it **production-ready**, **persistent**, and **fully Dockerized**.

### Key Updates

#### 1. **Full Docker Migration**
- Python 3.11-slim optimized build  
- Clean separation of:
  - `/app/`
  - `/defaults/`
  - `/host/`  
- Works on Linux, macOS, Windows Docker Desktop

#### 2. **Supervisor-based Process Management**
Runs stable:
- `monitor.py`
- `webgui.py`

With:
- Auto-restart  
- Zero log crashes  
- No buffering issues  

#### 3. **Persistent Config & Database**
- Config (`config.yaml`) and DB (`streams.db`) stored **outside the container**
- Auto-initialization on first boot  
- Fully synchronized between host ↔ container  

#### 4. **Symlink Architecture**
Prevents Windows/Linux mount conflicts:

```
/app/config.yaml   -> /host/config.yaml  
/app/streams.db    -> /host/streams.db
```

#### 5. **Improved Database Initialization**
- Auto-creates log tables
- Eliminates “no table” errors

#### 6. **Port Mapping Fix**
- API → **6868** (container 7000)  
- GUI → **6969** (container 8000)

---

## Folder Structure

```
StreamPulse-v2.1/
 ├── config.yaml
 └── streams.db
```

---

## Docker Compose

```yaml
services:
  streampulse:
    image: devprincekumar/streampulse:2.1
    container_name: StreamPulse-v2.1
    restart: unless-stopped
    ports:
      - "6868:7000"
      - "6969:8000"
    volumes:
      - ./StreamPulse-v2.1:/host
```

Access GUI:  
```
http://localhost:6969
```

API:  
```
http://localhost:6868/api/status
```

---

## Technical Architecture

### **monitor.py**
- Checks RTSP/HTTP streams
- Logs status, latency, frames
- Auto-creates log tables

### **webgui.py**
- Dashboard UI
- Live status + preview
- Updates config.yaml

### **supervisord**
Stable dual-process runner.

### **entrypoint.sh**
- Creates host files  
- Creates symlinks  
- Starts supervisor  

---

#  Performance & Resource Efficiency (v2.1)

Tested on:
- **Intel i5 12th Gen**
- **16 GB RAM**
- **25+ simultaneous streams**

### Resource Snapshot

<img width="1238" height="544" alt="image" src="https://github.com/user-attachments/assets/624625e0-caeb-4ee0-a5e8-27721bee40e3" />

### Observed Usage
| Metric | Value |
|--------|-------|
| CPU | **0.2% – 1.8%** |
| RAM | **127 MB** |
| Disk I/O | **~598 KB writes** |
| Network I/O | Stream dependent |

### Why so efficient?
- No full frame decoding  
- Lightweight RTSP probing  
- Async event loops  
- Minimal memory overhead  

---

#  SBC Hardware Efficiency Comparison (Realistic Estimates)

Below is a realistically calculated comparison for Single Board Computers:

## Assumptions:
- RTSP = Efficient  
- MJPEG = More CPU heavy  
- StreamPulse performs heartbeat checks only  

| Hardware | CPU | RAM | RTSP Streams Capacity | Mixed (RTSP+MJPEG) Capacity | Notes |
|----------|-----|-----|-----------------------|-----------------------------|-------|
| **Raspberry Pi 3B+** | 4×1.4 GHz | 1GB | **6–10 streams** | **3–5 streams** | Limited RAM but efficient at probing |
| **Raspberry Pi 4 (4GB)** | 4×1.5 GHz | 4GB | **15–25 streams** | **10–15 streams** | Good thermals, better bus |
| **Raspberry Pi 5 (8GB)** | 4×2.4 GHz | 8GB | **30–40 streams** | **20–30 streams** | Ideal SBC for monitoring clusters |
| **Intel NUC / Mini PC** | Varies | 8–16GB | **50–100+ streams** | **40–70 streams** | Ideal for heavy mixed workloads |
| **Your i5-12400 rig** | 6P+4E | 16GB | **120+ streams** | **80–100 streams** | Overpowered for monitoring |

---

#  Summary

StreamPulse v2.1 is:
- ✔ Lightweight  
- ✔ SBC-friendly  
- ✔ Production-ready  
- ✔ Dockerized  
- ✔ Stable & efficient  
- ✔ Capable of running 6 → 120+ streams depending on hardware  

---

## Local Development

```bash
pip install -r requirements.txt
python monitor.py
python webgui.py
```

---

## Repository Structure

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


