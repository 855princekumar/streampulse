# StreamPulse

## Lightweight Camera Stream Health Monitoring Microservice

<img width="1248" height="832" alt="banner" src="https://github.com/user-attachments/assets/337f7b48-75aa-40e5-840d-369170e113ac" />

<!-- Badges -->
![Stream Processing](https://img.shields.io/badge/Type-Stream%20Processing-6e40c9?style=flat-square&logo=apachespark)
![Python](https://img.shields.io/badge/Backend-Python-3776ab?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?style=flat-square&logo=fastapi)
![Docker](https://img.shields.io/badge/Container-Docker-2496ed?style=flat-square&logo=docker)
![Linux](https://img.shields.io/badge/Runtime-Linux-fcc624?style=flat-square&logo=linux&logoColor=black)
![Architecture](https://img.shields.io/badge/Architecture-Event%20Driven-ff6f00?style=flat-square)
![Observability](https://img.shields.io/badge/Focus-Observability-8a2be2?style=flat-square&logo=prometheus)
![Deployment](https://img.shields.io/badge/Deployment-Cloud%20Ready-326ce5?style=flat-square&logo=kubernetes)
![Status](https://img.shields.io/badge/Status-Actively%20Maintained-success?style=flat-square)


### Overview

**StreamPulse** is a minimal Python-based microservice for monitoring the operational health of heterogeneous IP camera networks.

It was designed during the expansion of a mixed-infrastructure deployment consisting of low-cost consumer cameras (such as TP-Link Tapo) and custom Raspberry Pi camera nodes running MotionEye. As the number of independent devices increased, conventional NVR monitoring and simple ping checks became insufficient to confirm real video availability or client accessibility.

To address this, StreamPulse implements a two-part architecture:

* **Monitor Service** – periodically connects to configured RTSP and MJPEG endpoints, captures a frame, and records the success or failure as a heartbeat log in an SQLite database.
* **Web GUI Service** – provides a Flask-based dashboard for configuration, visualization, and on-demand live frame verification.

A simple YAML configuration defines each stream’s name and URL. Both the monitor and the GUI read from this configuration, ensuring lightweight synchronization without external dependencies.

SQLite is used as the database to minimize hardware requirements and enable deployment on single-board computers (Raspberry Pi, Orange Pi, etc.).

---

### Problem Statement

Initial deployments used 9–10 cameras connected to an NVR, which was easy to supervise.

As the network scaled to include numerous standalone IP and MotionEye cameras, monitoring became difficult:

* Different stream formats and client limits
* Network pings could not confirm video availability
* Commercial NVR or VMS solutions were too heavy for mixed hardware

StreamPulse solves this by maintaining a reliable, real-time heartbeat for each camera and storing the results in a database for inspection and troubleshooting.

---

### Key Features

* Supports RTSP and MJPEG streams
* Logs stream reachability with timestamp and latency
* SQLite database backend for minimal resource usage
* Flask-based GUI for real-time monitoring and configuration
* YAML configuration for simple editing and automation
* Modular architecture (monitor / GUI / MQTT)
* Optimized for low-spec IoT or edge devices

---

### Architecture

```
                          ┌────────────────────────────────┐
                          │         Web GUI (Flask)        │
                          │  - Dashboard & Config Editor   │
                          │  - Live Frame Preview          │
                          └───────────────┬────────────────┘
                                          │
                                 REST API / SQLite
                                          │
    ┌───────────────────────┬─────────────┴───────────────┬────────────────────────┐
    │                       │                             │                        │
    │                       │                             │                        │
┌──────────────┐     ┌───────────────┐            ┌────────────────┐         ┌───────────────┐
│ Monitor      │     │ SQLite DB     │            │ MQTT Service   │         │ MQTT Broker   │
│ Service      │     │ (streams.db)  │            │ (mqtt_service) │         │ (external)    │
│ - Periodic   │     │ - Persistent  │            │ - Publishes    │         │ HiveMQ/etc.   │
│   RTSP/MJPEG │     │   heartbeat   │            │   JSON status  │         │               │
│   probing    │     │   logs        │            │ - Hot reload   │         │               │
│ - Writes to  │     │               │            │   config.yaml  │         │               │
│   database   │     │               │            │ - Reconnect    │         │               │
└──────────────┘     └───────────────┘            └────────────────┘         └───────────────┘

```

---

### What’s New in Version 2.2

Version 2.2 introduces a **third microservice** to StreamPulse: an optional **MQTT status publisher** designed for dashboards, IoT systems, cloud monitoring, and analytics pipelines.

Key additions:

* New `mqtt_service.py` microservice managed by Supervisor
* Hot-reload of MQTT configuration from `config.yaml`
* Supports TCP, WebSocket, TLS, and TLS-WebSocket
* Automatic reconnect with exponential backoff
* Graceful shutdown and safe thread termination
* Publishes per-stream JSON heartbeat data
* MQTT settings fully integrated into the Web GUI
* Docker image now runs **three** independent services
* MQTT failures no longer affect the monitor or GUI
* Cleaner logs and improved exception handling

---

### MQTT Testing Script (Optional Utility)

A minimal subscriber script is included to help users validate MQTT broker connectivity and ensure StreamPulse is publishing correctly.

**Steps:**

1. Enable MQTT in `config.yaml` or via the GUI.
2. Match the MQTT topic used by StreamPulse.
3. Save the script as `mqtt_test_subscriber.py` and run it.

```python
#!/usr/bin/env python3
import paho.mqtt.client as mqtt
import json

BROKER = "broker.hivemq.com"
PORT = 1883
TOPIC = "stream_monitor/status"
USERNAME = ""
PASSWORD = ""

def on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code == 0:
        print(f"[MQTT] Connected → subscribing to '{TOPIC}'")
        client.subscribe(TOPIC)
    else:
        print(f"[MQTT] Connection failed (code={reason_code})")

def on_message(client, userdata, msg):
    print("\n----------------------------")
    print(f"[MQTT] Message received on: {msg.topic}")
    try:
        print(json.dumps(json.loads(msg.payload.decode()), indent=2))
    except Exception:
        print(msg.payload.decode())
    print("----------------------------\n")

def main():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    if USERNAME:
        client.username_pw_set(USERNAME, PASSWORD)
    client.on_connect = on_connect
    client.on_message = on_message

    print(f"[MQTT] Connecting to {BROKER}:{PORT} ...")
    client.connect(BROKER, PORT, keepalive=30)
    print("[MQTT] Listening... Press Ctrl+C to stop.")
    client.loop_forever()

if __name__ == "__main__":
    main()
```

---

### Version Map (Updated)

| Version  | Folder                                      | Description                                               |
| -------- | ------------------------------------------- | --------------------------------------------------------- |
| **v2.2** | [`version-2.2/`](./version-2.2)             | Latest feature release with MQTT publisher microservice   |
| **v2.1** | [`version-2.1/`](./version-2.1)             | Dockerized release with Supervisor and persistent storage |
| v2.0     | [`version-2/`](./version-2)                 | Async engine + improved GUI                               |
| v1.1     | [`version-1/`](./version-1/)                | First GUI microservice (Docker supported)                 |
| v0.5     | [`legacy_prototypes/`](./legacy-prototypes) | Early standalone scripts                                  |

---

### Configuration Example

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

### Usage (Local)

```bash
pip install -r requirements.txt
python monitor.py
python webgui.py
python mqtt_service.py
```

GUI: [http://localhost:8000](http://localhost:8000)
Default credentials: `admin / admin123`

---

### Manual Docker Deployment (Updated for v2.2)

```bash
docker pull devprincekumar/streampulse:2.2

docker run -d \
  -p 6969:8000 \
  -p 6868:7000 \
  -v $(pwd)/StreamPulse-v2.2:/host \
  --name streampulse-v2.2 \
  devprincekumar/streampulse:2.2
```

---

## Docker Compose Deployment (Updated for v2.2)

```bash
docker compose up -d
```

Starts:

* monitor service
* web GUI
* MQTT service

---

## Persistent Data Storage (Updated for v2.2)

```
StreamPulse-v2.2/
 ├── config.yaml
 └── streams.db
```

These files survive container rebuilds and updates.

---

## Default Access

* GUI: [http://localhost:6969](http://localhost:6969)
* API: [http://localhost:6868/api/status](http://localhost:6868/api/status)
* Credentials: `admin / admin123`

---

## Technical Notes (Updated)

* Docker images:

  * `streampulse:2.2` (latest, with MQTT)
  * `streampulse:2.1` (stable fallback)
  * `streampulse:1.1` (legacy)

* Python 3.11

* Supervisor orchestrates **three independent services** in v2.2

* Hot-reload config + safe DB initialization

* Built for Raspberry Pi and edge hardware

---

## Legacy Prototypes and Evolution

(unchanged; kept accurate)

---

### Current Status

Version **2.2** is the recommended and most complete release.

Version **2.1** remains a stable fallback for users who do not require MQTT integration.

Legacy versions remain available for reference and compatibility testing.

---

### License

MIT License © 2025 Prince Kumar

---


