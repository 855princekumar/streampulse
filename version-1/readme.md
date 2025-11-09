# StreamPulse v1.1 – Initial GUI-Based Microservice

This version represents the **first stable release** of StreamPulse, introducing a modular two-part architecture for monitoring the operational health of heterogeneous IP camera networks using **RTSP** and **MJPEG** streams.

---

##  Overview

StreamPulse v1 combined a lightweight backend service for camera health monitoring with a **Flask-based Web GUI** for visualization and configuration.

It was designed to handle small-to-medium camera deployments (up to ~100 streams) on single-board computers such as the Raspberry Pi.

---

##  Core Features

- **RTSP & MJPEG Support** – Heartbeat check for each stream type  
- **Frame Capture Test** – Verifies camera activity by fetching a frame per cycle  
- **SQLite Logging** – Records status, timestamp, and latency for each stream  
- **Flask Web GUI** – Real-time dashboard to view stream uptime and last check  
- **Config File Sync** – YAML-based configuration for easy editing and portability  
- **Threaded Monitoring** – Parallelized stream health checks for efficiency  
- **Docker-Ready Build** – Official `devprincekumar/streampulse:1.1` image for instant deployment  

---

##  GUI Overview

The web interface introduced the core visualization layer of StreamPulse:
- Color-coded status (🟢 Healthy, 🔴 Offline)
- Last checked timestamp and latency
- Stream names and corresponding protocols (RTSP/MJPEG)
- Configurable heartbeat interval via settings
- Simple admin login (`admin / admin123`)

<p align="center">
 <img width="1282" height="535" alt="image" src="https://github.com/user-attachments/assets/a327f9e1-3246-4657-8f6e-d546bddf3008" />
 <img width="1522" height="518" alt="image" src="https://github.com/user-attachments/assets/33b8cae4-7a3e-4de7-9a5e-972860ed6ee3" />
 <img width="763" height="786" alt="image" src="https://github.com/user-attachments/assets/251508b5-9075-4931-9ef0-199c80189154" />
</p>

---

##  Test Streams

For users without their own cameras, v1 supported testing with public sources from:
🔗 [Insecam – Public IP Cameras Directory](http://www.insecam.org/en/byrating/#google_vignette)

Example YAML:
```yaml
streams:
  - name: TestCam
    url: http://91.191.213.49:8081/mjpg/video.mjpg
```


