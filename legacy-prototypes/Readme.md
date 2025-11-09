# Legacy Prototypes – StreamPulse Development Journey

This folder contains the **early standalone scripts** that led to the development of the StreamPulse microservice and web dashboard.

Each script explored different aspects of stream health monitoring — such as OpenCV frame capture, system resource tracking, latency logging, and multi-threaded parallel camera testing.

---

### Prototype Overview

| File | Description |
|------|--------------|
| **1-working-rtsp-log-(cv).py** | One of the earliest RTSP logging experiments. Used OpenCV to fetch frames, record timestamps, and analyze connectivity stability. |
| **2-me-stream-receive.py** | Designed to receive and store MJPEG streams from MotionEye servers. It logs CPU, memory, and network metrics while chunking short video segments for post-analysis. |
| **3-rtsp_sender_logger.py** | Simulated an RTSP camera by sending a live feed using FFmpeg. Added NTP-synced timestamps and monitored CPU/network stats during transmission. |
| **3-rtsp_receiver_logger.py** | Captured and analyzed RTSP frames for latency and jitter metrics, logging all stats into a CSV for further study. |
| **4-rtsp_heartbest.py** | Multi-threaded RTSP “heartbeat” tool to check many cameras in parallel. Each device produced its own CSV log, making it the conceptual base of StreamPulse’s monitoring logic. |

---

### Key Learnings

- NTP time synchronization was critical for accurate latency measurement.
- OpenCV offered flexibility but had performance limits on low-spec hardware.
- FFmpeg proved more stable for long-term stream generation and encoding.
- Threaded stream polling needed optimization — later replaced by hybrid async scheduling.
- CSV logs evolved into a persistent SQLite database for efficiency and reliability.

---

### Legacy → StreamPulse Transition

These prototypes shaped the **StreamPulse v1** architecture:
- Real-time health checks evolved from the RTSP heartbeat system.
- Data logging and timestamping techniques inspired the SQLite model.
- Stream type differentiation (RTSP vs MJPEG) originated from the MotionEye receiver.
- NTP time sync and latency recording became core diagnostic tools.

Each version taught a new lesson in scalability, reliability, and low-level performance that led to today’s stable and extensible version of StreamPulse.

---

**Author:** Prince Kumar  
**Year:** 2024–2025  
**License:** MIT
