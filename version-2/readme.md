# StreamPulse v2.0 – Hybrid Async & Secure Architecture

Version 2 marks a **major architectural evolution** of StreamPulse — transitioning from a threaded system to a **hybrid async microservice**, designed for performance, scalability, and security across hundreds of RTSP and MJPEG camera streams.

---

##  Overview

Building on v1’s success, StreamPulse v2 integrates an asynchronous event loop for stream checking, with independent RTSP/MJPEG handlers and secure, persistent configurations.

This version is optimized for **IoT-scale deployments** and designed to run continuously on edge or SBC hardware.

---

##  Key Enhancements

- **Hybrid Async + Threaded Engine** – Stable and scalable monitoring loop  
- **Parallel RTSP & MJPEG Schedulers** – Separate adaptive task pools  
- **Auto NTP & Timezone Sync** – Ensures precise timestamp logging  
- **Secure Admin Login** – Password stored in SQLite, configurable via GUI  
- **Dynamic GUI Dashboard** – Auto-refreshing real-time view with uptime color codes  
- **Live Preview Feature** – Fetches 5-second live stream on demand without blocking  
- **CSV Export** – Download all log data for external analysis  
- **Color Indicator Reference Panel** – Built-in guide for status meaning  
- **Responsive Design** – Dark/light toggle, mobile and tablet friendly  
- **Docker Optimized** – Built on Alpine for lightweight deployment  

---

##  GUI Enhancements

The redesigned interface focuses on real-time responsiveness and better scalability:
- Clear color-coded uptime badges (🟢, 🟡, 🔴)
- Protocol labels (RTSP / MJPEG)
- Clickable history modal for per-stream logs
- Stream preview option (5s live check)
- Timezone setting & sync status indicator
- Export logs button and settings access control
- Info modal explaining health color codes

---

##  Test Streams

You can test v2 with public camera sources:

🔗 [Insecam – Public IP Cameras Directory](http://www.insecam.org/en/byrating/#google_vignette)

Example `config.yaml`:
```yaml
streams:
  - name: GateCam
    url: rtsp://user:pass@192.168.1.1:554/stream1
  - name: PublicMJPEG
    url: http://91.191.213.49:8081/mjpg/video.mjpg
```

---

## 🐳 Docker Deployment

Deploy the latest version instantly:
```bash
docker pull devprincekumar/streampulse:2.0
docker run -d -p 8000:8000 -v $(pwd)/data:/data devprincekumar/streampulse:2.0
```

Access dashboard: [http://localhost:8000](http://localhost:8000)

**Default Credentials:** `admin / admin123`

---

##  Under the Hood

- Adaptive round-robin stream scheduler  
- Error-based retry backoff for unstable feeds  
- Automatic DB schema updates  
- Persistent `/data` volume for config + logs  
- Tested up to **1,000 camera streams** on mixed RTSP/MJPEG inputs  

---

# GUI Snippets

<img width="341" height="318" alt="1-login" src="https://github.com/user-attachments/assets/107afeae-cebe-48f5-84c4-ef5343f90b3d" />
<img width="760" height="129" alt="5-color-logics" src="https://github.com/user-attachments/assets/f2bb6826-1ec0-4fbf-8524-b26716fbb551" />
<img width="762" height="751" alt="3 3-rtsp-stream-history" src="https://github.com/user-attachments/assets/cbac1eb8-aee7-4616-b923-c07f2190a851" />
<img width="757" height="435" alt="3 2-mjpeg-stream-history" src="https://github.com/user-attachments/assets/9dd889be-611a-4040-9d80-793f1a77af07" />
<img width="949" height="625" alt="3 1-rtsp-live-preview" src="https://github.com/user-attachments/assets/c3a7e8ae-df0c-4336-a948-bbab04fa4b3e" />
<img width="949" height="779" alt="3 0-mjpeg-live-preview" src="https://github.com/user-attachments/assets/8ce6d966-ff74-48b1-b5b4-24137a2b9188" />
<img width="976" height="929" alt="2-main dashboard" src="https://github.com/user-attachments/assets/c6bb1bfa-1398-4da5-9f34-90acd899dc37" />

---

##  Notes

v2 resolves limitations observed during live field testing of v1 — improving connection handling, stability, and GUI responsiveness.  
It’s now a production-ready monitoring layer for heterogeneous camera networks.

---

**Release:** v2.0  
**Date:** November 2025  
**License:** MIT © Prince Kumar  

---
