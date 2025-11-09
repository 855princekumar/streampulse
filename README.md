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

StreamPulse provides a lightweight, hardware-agnostic alternative that records the operational state of each stream as a “heartbeat” with accurate timestamps (NTP-synchronized). This allows technical teams to identify failures—power, network, or configuration—without manual inspection.

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

### GUI Snippets

<img width="1282" height="535" alt="image" src="https://github.com/user-attachments/assets/a327f9e1-3246-4657-8f6e-d546bddf3008" />
<img width="1522" height="518" alt="image" src="https://github.com/user-attachments/assets/33b8cae4-7a3e-4de7-9a5e-972860ed6ee3" />
<img width="763" height="786" alt="image" src="https://github.com/user-attachments/assets/251508b5-9075-4931-9ef0-199c80189154" />

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

### 🐳 Manual Docker Deployment

To pull and run the container manually:

```bash
docker pull devprincekumar/streampulse:1.1

docker run -d -p 8000:8000 -v $(pwd)/data:/data devprincekumar/streampulse:1.1
```

Once the container is running, open:
```
 [http://localhost:8000](http://localhost:8000)
```

##  Docker Compose Deployment

You can also deploy using **Docker Compose** for easier management:

```bash
docker compose up -d
```

This will automatically start the **StreamPulse** web GUI and monitoring services.

---

##  Persistent Data Storage

All persistent data — including configuration files (`config.yaml`) and the SQLite database (`streams.db`) — are stored in the local `data/` folder on the host system.

This ensures that all settings, logs, and stream configurations remain intact across container restarts or image updates.

---

##  Default Access

- **URL:** [http://localhost:8000](http://localhost:8000)  
- **Default Credentials:** `admin / admin123`

---

###  Test Streams (for First-Time Users)

If you don’t have your own camera setup yet, you can easily test StreamPulse with publicly available live streams.

A great source for open camera feeds:  
🔗 [Insecam – Public IP Cameras Directory](http://www.insecam.org/en/byrating/#google_vignette)

You can copy any **RTSP** or **MJPEG** URL from that site and add it in your `config.yaml` or through the web GUI.

**Example entry in `config.yaml`:**
```yaml
streams:
  - name: TestCam
    url: http://91.191.213.49:8081/mjpg/video.mjpg
```

Once added, restart StreamPulse or reload the dashboard — you’ll see the camera’s health status live in the GUI.

### Note: These streams are publicly shared by their operators. You can use them responsibly and for testing purposes only.
---

## Technical Notes

- Image: `devprincekumar/streampulse:1.1`  
- Built with Python 3.11 and Flask  
- Includes sample stream for first-run testing  
- Lightweight — suitable for Raspberry Pi or edge devices  
- Each stream has a dedicated log table within `streams.db`.  
- Logs are timestamped using NTP-synchronized UTC time and mapped to the configured timezone.  
- Designed to run continuously on low-power devices.  
- No external database or message broker required.  

---

### Current Status

Version 1 implements a functional threaded architecture suitable for up to a few hundred streams under normal heartbeat intervals.  
Further improvements and scalability enhancements are planned as subsequent versions are tested and validated in live environments.

---

### License

MIT License © 2025 Prince Kumar
