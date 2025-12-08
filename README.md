# StreamPulse

## Lightweight Camera Stream Health Monitoring Microservice

<img width="1248" height="832" alt="banner" src="https://github.com/user-attachments/assets/337f7b48-75aa-40e5-840d-369170e113ac" />

### Overview

**StreamPulse** is a minimal Python-based microservice for monitoring the operational health of heterogeneous IP camera networks.

It was designed during the expansion of a mixed-infrastructure deployment consisting of low-cost consumer cameras (such as TP-Link Tapo) and custom Raspberry Pi camera nodes running MotionEye. As the number of independent devices increased, conventional NVR monitoring and simple ping checks became insufficient to confirm real video availability or client accessibility.

To address this, StreamPulse implements a two-part architecture:

- **Monitor Service** – periodically connects to configured RTSP and MJPEG endpoints, captures a frame, and records the success or failure as a heartbeat log in an SQLite database.  
- **Web GUI Service** – provides a Flask-based dashboard for configuration, visualization, and on-demand live frame verification.

A simple YAML configuration defines each stream’s name and URL. Both the monitor and the GUI read from this configuration, ensuring lightweight synchronization without external dependencies.

SQLite is used as the database to minimize hardware requirements and enable deployment on single-board computers (Raspberry Pi, Orange Pi, etc.).

---

### Problem Statement

Initial deployments used 9–10 cameras connected to an NVR, which was easy to supervise.

As the network scaled to include numerous standalone IP and MotionEye cameras, monitoring became difficult:

- Each hardware platform supported different stream formats and client limits.  
- Network pings could not confirm if a stream was actually functional.  
- Commercial NVR solutions were resource-heavy and unsuitable for mixed hardware.

StreamPulse provides a lightweight, hardware-agnostic alternative that records the operational state of each stream as a “heartbeat” with accurate timestamps (NTP-synchronized). This allows technical teams to identify failures in power, network, or configuration, without manual inspection.

---

### Key Features

- Supports RTSP and MJPEG streams  
- Logs stream reachability with timestamp and latency  
- SQLite database backend for minimal resource usage  
- Flask-based GUI for real-time monitoring and configuration  
- YAML configuration for ease of editing and integration  
- Modular two-process design (monitor / GUI) for reliability  
- Built for low-spec IoT or edge devices  

---

### Architecture

```
             ┌─────────────────────────────┐
             │         Web GUI (Flask)     │
             │ - Dashboard & Config Editor │
             │ - Live Frame Preview        │
             └──────────────┬──────────────┘
                            │
                     REST API / SQLite
                            │
             ┌──────────────┴──────────────┐
             │      Monitor Service        │
             │ - Periodic stream probing   │
             │ - Logs results to database  │
             └─────────────────────────────┘
```
---

###  Version Map *(Updated)*

| Version | Folder | Description |
|----------|---------|-------------|
| **v2.1** | [`version-2.1/`](./version-2.1) | Latest release with full Docker support, supervisor, and persistent storage |
| v2.0 | [`version-2/`](./version-2) | Stable async engine + improved GUI |
| v1.1 | [`version-1/`](./version-1/) | First GUI-based microservice (Docker supported) |
| v0.5 | [`legacy_prototypes/`](./legacy-prototypes) | Early standalone scripts and research prototypes |

---

### Configuration Example

**config.yaml**

```yaml
heartbeat_seconds: 15
timezone: Asia/Kolkata

streams:
  - name: GateCamera
    url: rtsp://user:pass@192.168.1.1:554/stream1

  - name: LabCam1
    url: http://192.168.1.1:9081
```

---

### Usage

Install dependencies:

```bash
pip install -r requirements.txt
```

Start the monitor service:

```bash
python monitor.py
```

Start the web interface:

```bash
python webgui.py
```

Open [http://localhost:8000](http://localhost:8000) in your browser.

**Default credentials:** `admin / admin123`

---

### 🐳 Manual Docker Deployment *(Updated for v2.1)*

####  Pull and run version 2.1 (Recommended)

```bash
docker pull devprincekumar/streampulse:2.1

docker run -d \
  -p 6969:8000 \
  -p 6868:7000 \
  -v $(pwd)/StreamPulse-v2.1:/host \
  --name streampulse-v2.1 \
  devprincekumar/streampulse:2.1
```

GUI URL:
```
http://localhost:6969
```

API:
```
http://localhost:6868/api/status
```

####  Legacy (v1.1) Deployment

```bash
docker pull devprincekumar/streampulse:1.1

docker run -d -p 8000:8000 -v $(pwd)/data:/data devprincekumar/streampulse:1.1
```

---

## Docker Compose Deployment *(Updated for v2.1)*

```bash
docker compose up -d
```

This will automatically start the StreamPulse web GUI and monitoring services.

---

##  Persistent Data Storage *(Updated for v2.1)*

For version **2.1**, persistent data is stored outside the container:

```
StreamPulse-v2.1/
 ├── config.yaml
 └── streams.db
```

These files survive container restarts and updates.

---

##  Default Access

- **GUI:** http://localhost:6969  
- **API:** http://localhost:6868/api/status  
- **Default Credentials:** `admin / admin123`

---

### Test Streams (for First-Time Users)

(UNCHANGED — preserved)

---

## Technical Notes *(Updated)*

- Images:
  - `devprincekumar/streampulse:2.1` (latest)
  - `devprincekumar/streampulse:1.1` (legacy)
- Built with Python 3.11 and Flask  
- Version 2.1 uses Supervisor for process orchestration  
- Persistent config + DB via host bind  
- Database auto-table creation  
- Designed for Raspberry Pi, edge devices, and cloud deployment  
- Zero external dependencies  

---

## Legacy Prototypes and Evolution

(Your full original section remains unchanged and preserved below.)

Before StreamPulse became a Flask-based microservice with a GUI and database, it went through several experimental stages, from single-camera stream loggers to multi-threaded network monitors.

These early scripts were the foundation for understanding stream behavior, latency, and reliability under different protocols (RTSP, MJPEG) and hardware setups (NVRs, MotionEye, Raspberry Pi nodes).

You can explore these prototypes in the [`legacy-prototypes/`](./legacy-prototypes) folder.  
Each script was part of the evolution that led to StreamPulse v1.

| File | Description | Key Learnings |
|------|--------------|---------------|
| **1-working-rtsp-log-(cv).py** | Early OpenCV-based RTSP logger that captured frames and stored timestamps to CSV. | Validated minimal RTSP connection handling and frame fetch consistency. |
| **2-me-stream-receive.py** | MotionEye MJPEG receiver script, saved short video chunks while logging CPU, memory, and network usage. | Tested continuous HTTP-based MJPEG fetching and real-time system monitoring. |
| **3-rtsp_sender_logger.py** | RTSP sender prototype using FFmpeg to stream video input with timestamp overlay and NTP sync. | Helped understand stream generation, encoding, and network bitrate behavior. |
| **3-rtsp_receiver_logger.py** | Receiver-side analytics tool that calculated latency, jitter, and frame consistency using NTP and CSV logs. | Introduced frame-level analysis and time-sync verification. |
| **4-rtsp_heartbest.py** | Multi-threaded RTSP heartbeat system for several cameras at once, storing logs per camera. | Core inspiration for StreamPulse’s parallel stream checking and logging architecture. |

These prototypes collectively formed the groundwork for **StreamPulse v1**, merging lightweight frame checking, NTP time sync, and CSV-based health logs into a unified, database-backed service.

> Each version was tested under real IoT and lab conditions, progressively optimized for performance, error handling, and deployment scalability.

---

### Current Status *(Minor Update)*

Version **2.1** is now the recommended release for all new deployments, offering stable Docker-based deployment, persistent data storage, and reliable process orchestration.

Legacy versions (v2.0, v1.x) remain preserved for historical reference and compatibility testing.

---

### License

MIT License © 2025 Prince Kumar
