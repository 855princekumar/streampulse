# StreamPulse v2.1.1 (SLA Monitoring Release)

A lightweight **RTSP/HTTP stream heartbeat monitoring dashboard** with live status, logging, preview, persistent storage, and **Prometheus-based SLA monitoring**.

Version **2.1.1** builds on the production-ready Docker architecture introduced in **v2.1**, adding **observability features designed for modern monitoring stacks such as Prometheus and Grafana**.

---

# What’s New in Version 2.1.1

Version **2.1.1** extends the stable architecture introduced in **v2.1** by introducing **native monitoring endpoints and SLA analytics**.

The goal of this release is to make StreamPulse usable not only as a dashboard but also as a **reliable infrastructure monitoring service**.

---

## Key Additions

### 1. Prometheus Metrics Endpoint

StreamPulse now exposes a **Prometheus-compatible metrics endpoint**.

```
http://<host>:6969/metrics
```

Prometheus can scrape this endpoint directly without any additional exporters.

Example metrics exposed:

```
stream_up
stream_latency_ms
stream_last_seen_age_seconds
stream_uptime_streak_seconds
system_total_streams
system_ok_streams
system_fail_streams
system_up
system_ok_samples_30d
system_total_samples_30d
system_sla_ratio_30d
```

These metrics allow monitoring systems to track:

* stream uptime
* network latency
* stream failures
* overall infrastructure reliability

---

### 2. System-wide SLA Monitoring

StreamPulse now computes **sample-based SLA metrics** across all monitored streams.

Example output:

```
system_total_streams 17
system_ok_streams 11
system_fail_streams 6
system_sla_ratio_30d 0.806223
```

Meaning:

* **17 streams monitored**
* **11 currently operational**
* **6 currently failing**
* **overall 30-day SLA ≈ 80.6%**

This makes StreamPulse suitable for monitoring:

* campus surveillance systems
* smart city camera networks
* distributed IoT deployments
* edge video monitoring systems

---

### 3. REST Monitoring API

The REST API provides real-time JSON status information.

```
http://<host>:6969/api/status
```

This endpoint is useful for:

* automation scripts
* health checks
* external monitoring tools
* custom alerting pipelines

---

### 4. Observability-first Deployment

StreamPulse v2.1.1 integrates cleanly with modern monitoring stacks.

Typical architecture:

```
IP Cameras
     │
     ▼
StreamPulse
     │
     │ Prometheus scrape
     ▼
Prometheus
     │
     ▼
Grafana Dashboard
```

Operators can visualize:

* camera uptime trends
* latency spikes
* stream failures
* SLA compliance

---

### 5. Simplified Architecture (No MQTT)

Unlike **v2.2**, version **2.1.1 does not include MQTT publishing**.

This version focuses on:

* lightweight monitoring deployments
* minimal resource usage
* observability-first architecture

---

# Folder Structure (Persistent Storage)

When running Docker Compose, the following folder is created:

```
StreamPulse-v2.1.1/
 ├── config.yaml
 └── streams.db
```

These files persist across container restarts and upgrades.

---

# Docker Compose (Monitoring Deployment)

```
services:
  streampulse:
    image: devprincekumar/streampulse:2.1.1-sla-ready
    container_name: StreamPulse-v2.1.1
    restart: unless-stopped

    ports:
      - "6969:8000"

    volumes:
      - ./StreamPulse-v2.1.1:/host
```

Run with:

```
docker compose up -d
```

---

# Monitoring Endpoints

### Web GUI

```
http://localhost:6969
```

---

### Status API

```
http://localhost:6969/api/status
```

---

### Prometheus Metrics

```
http://localhost:6969/metrics
```

---

# Technical Architecture

## monitor.py

The monitoring engine responsible for stream probing.

Functions:

* periodically checks RTSP / HTTP streams
* measures latency
* logs stream status
* stores heartbeat logs in SQLite
* auto-creates missing log tables
* reloads configuration dynamically

---

## webgui.py

Provides the monitoring dashboard.

Features:

* live stream status
* configuration editor
* stream preview
* monitoring history
* configuration synchronization

---

## Prometheus Metrics Export

Metrics are generated from monitoring data stored in SQLite.

Per-stream metrics:

* availability (`stream_up`)
* latency (`stream_latency_ms`)
* last activity (`stream_last_seen_age_seconds`)
* uptime streak (`stream_uptime_streak_seconds`)

System metrics:

* total streams
* operational streams
* failed streams
* system SLA ratio

---

## supervisord

Supervisor manages both core services.

```
monitor.py
webgui.py
```

Supervisor ensures:

* automatic restart
* crash recovery
* stable multi-process execution

---

## entrypoint.sh

Startup tasks include:

* verifying host configuration
* copying default configuration if missing
* initializing database
* creating symlinks

```
/app/config.yaml → /host/config.yaml
/app/streams.db → /host/streams.db
```

This ensures persistent storage and cross-platform compatibility.

---

# The Journey from v2.1 → v2.1.1

Version **2.1.1** builds directly on the stable architecture introduced in **v2.1**.

---

## Stable Monitoring Core

v2.1 solved major reliability issues including:

* Docker-based deployment
* persistent configuration
* container-safe database
* supervisor process management
* cross-platform compatibility

This foundation remains unchanged.

---

## Observability Gap

While v2.1 provided a monitoring dashboard, it lacked integration with infrastructure monitoring tools.

Operators needed visibility through systems such as:

* Prometheus
* Grafana
* centralized monitoring platforms

---

## Observability Layer

Version **2.1.1 introduces native metrics export**, enabling StreamPulse to act as a monitoring target.

The system now exposes:

* stream health metrics
* system-wide uptime
* rolling SLA calculations

---

# Grafana Dashboard Example

Once Prometheus is scraping the `/metrics` endpoint, Grafana can visualize StreamPulse metrics.

---

## Example Prometheus Scrape Configuration

Add to `prometheus.yml`:

```
scrape_configs:
  - job_name: "streampulse"
    metrics_path: /metrics
    static_configs:
      - targets: ["localhost:6969"]
```

Restart Prometheus after editing.

---

# Example Grafana Panels

### System SLA

PromQL:

```
system_sla_ratio_30d * 100
```

Recommended panel: **Gauge**

---

### Total vs Failed Streams

PromQL:

```
system_total_streams
system_fail_streams
```

Recommended panel: **Bar Gauge**

---

### Stream Availability

PromQL:

```
stream_up
```

Recommended panel: **State Timeline**

---

### Stream Latency

PromQL:

```
stream_latency_ms
```

Recommended panel: **Time Series**

---

### Stream Uptime Streak

PromQL:

```
stream_uptime_streak_seconds
```

Recommended panel: **Stat**

---

# Example Dashboard Layout

```
┌──────────────────────────────┐
│ System SLA (Gauge)           │
└──────────────────────────────┘

┌──────────────┬──────────────┐
│ Total Streams│Failed Streams│
└──────────────┴──────────────┘

┌──────────────────────────────┐
│ Stream Availability Timeline │
└──────────────────────────────┘

┌──────────────────────────────┐
│ Stream Latency Graph         │
└──────────────────────────────┘
```

---

# Final Result

StreamPulse v2.1.1 provides:

* fully Dockerized deployment
* persistent configuration
* stable monitoring engine
* Prometheus metrics endpoint
* system-wide SLA monitoring
* Grafana integration
* lightweight resource usage
* compatibility with edge devices

---

# Local Development (without Docker)

```
pip install -r requirements.txt
python monitor.py
python webgui.py
```

---

# Repository Structure

```
version-2.1.1/
├── monitor.py
├── webgui.py
├── config.yaml
├── streams.db
├── supervisord.conf
├── entrypoint.sh
├── Dockerfile
└── docker-compose.yml
```

---

# License

MIT License
© Prince Kumar
