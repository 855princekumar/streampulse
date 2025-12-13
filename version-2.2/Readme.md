
# StreamPulse v2.2

A lightweight RTSP/HTTP stream heartbeat monitoring and MQTT publishing system designed for local or production deployments.
Includes a web dashboard, persistent configuration, and stable multi-service execution using Docker and Supervisor.

---

# 1. Overview of Version 2.2

Version 2.2 introduces major architectural improvements, better stability, and a new MQTT publishing service.
The system now runs three coordinated services inside Docker:

1. monitor.py – performs regular RTSP/HTTP health checks
2. webgui.py – provides the configuration and monitoring dashboard
3. mqtt_service.py – publishes status JSON to an MQTT broker

All services run under Supervisor with restart policies and clean logging.

---

# 2. New Features in v2.2

## 2.1 MQTT Publishing Service (New)

A dedicated microservice that publishes `/api/status` output to an MQTT broker.

Features:

* Full MQTT TCP/WebSocket/TLS support
* Configurable broker parameters
* Configurable topic name
* Adjustable publish interval (minimum 5 seconds)
* Username/password support
* Automatic reconnection
* Hot-reload of config.yaml

---

## 2.2 Three-Service Architecture

StreamPulse now runs as three independent but coordinated services:

| Service         | Function                                     |
| --------------- | -------------------------------------------- |
| monitor.py      | Performs heartbeat, logs status to SQLite    |
| webgui.py       | Configuration UI, preview, stream management |
| mqtt_service.py | Publishes current status JSON to MQTT        |

All services are managed by Supervisor for controlled startup and restarts.

---

## 2.3 Improved Docker Build

The Dockerfile was rewritten for:

* Smaller image size
* Deterministic builds
* Clean dependency installation
* Automatic configuration and DB initialization
* Stable execution on Linux, macOS, and Windows

---

## 2.4 Persistent Storage

All user-modifiable files are stored outside the container:

```
/host/config.yaml
/host/streams.db
```

StreamPulse links them into the application directory:

```
/app/config.yaml -> /host/config.yaml
/app/streams.db  -> /host/streams.db
```

This ensures that configuration and history survive upgrades and container rebuilds.

---

# 3. Folder Structure (Persistent Host Storage)

When running under Docker Compose, the following directory is created:

```
StreamPulse-v2.2/
 ├── config.yaml
 └── streams.db
```

---

# 4. Docker Compose (Production Setup)

```yaml
services:
  streampulse:
    build: .
    container_name: streampulse-v2.2
    restart: unless-stopped

    ports:
      - "6868:7000"   # Monitor API
      - "6969:8000"   # Web GUI

    volumes:
      - ./StreamPulse-v2.2:/host
```

Start the service:

```
docker compose up -d
```

Access Web GUI:

```
http://localhost:6969
```

API Status:

```
http://localhost:6868/api/status
```

MQTT Output (default):

```
topic: streampulse/status
```

---

# 5. Technical Architecture

## 5.1 monitor.py

* Performs periodic stream health checks
* Writes status, latency, and message to SQLite tables
* Creates missing tables automatically
* Reads config.yaml at runtime

## 5.2 webgui.py

* Provides a full dashboard for monitoring
* Live updates every 5 seconds
* Preview function for MJPEG/RTSP
* Stream editor and deletion
* MQTT configuration editor
* Writes config.yaml safely

## 5.3 mqtt_service.py

* Reads status from local API endpoint
* Publishes as JSON to MQTT broker
* Supports TCP, WebSocket, TLS modes
* Optional username/password
* Minimum interval: 5 seconds
* Automatic reconnect logic
* Reloads config.yaml without restart

## 5.4 Supervisor

Handles startup and health of the three services:

* Auto-restart on crash
* Independent service control
* Clean logging without rotation issues

## 5.5 entrypoint.sh

* Ensures /host folder contains config.yaml and streams.db
* Copies defaults from image if missing
* Creates symlinks into /app
* Launches Supervisor

---

# 6. Local Development (Non-Docker)

```
pip install -r requirements.txt

python monitor.py
python webgui.py
python mqtt_service.py
```

---

# 7. Repository Layout

```
/
├── monitor.py
├── webgui.py
├── mqtt_service.py
├── config.yaml
├── streams.db
├── supervisord.conf
├── entrypoint.sh
├── Dockerfile
└── docker-compose.yml
```

---
