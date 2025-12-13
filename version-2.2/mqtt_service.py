#!/usr/bin/env python3
"""
mqtt_service.py
Robust MQTT publisher that:
- reads /host/config.yaml (hot-reload)
- polls a status API and publishes raw JSON (string) to an MQTT topic
- supports TLS / websockets / username & password
- graceful shutdown and reconnect/backoff logic
- structured logging to stdout
"""

from __future__ import annotations
import os
import sys
import time
import json
import yaml
import ssl
import random
import signal
import requests
import logging
from pathlib import Path
from threading import Event, Thread
from typing import Any, Dict, Optional

try:
    import paho.mqtt.client as mqtt
except Exception:
    print("Missing dependency 'paho-mqtt'. Install with: pip install paho-mqtt", file=sys.stderr)
    raise

# ---------- Logging ----------
LOG = logging.getLogger("mqtt_service")
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-5s | %(message)s"))
LOG.addHandler(handler)
LOG.setLevel(logging.INFO)

# ---------- Constants & defaults ----------
CFG_PATH = Path(os.getenv("CFG_PATH", "/host/config.yaml"))
MIN_INTERVAL = 5  # seconds

DEFAULT_MQTT: Dict[str, Any] = {
    "enabled": False,
    "host": "broker.hivemq.com",
    "port": 1883,
    "ws_port": 8000,
    "tls_port": 8883,
    "tls_ws_port": 8884,
    "use_tls": False,
    "use_websocket": False,
    "username": None,
    "password": None,
    "client_id": None,
    "topic": "stream_monitor/status",
    "qos": 0,
    "retain": False,
    "interval_seconds": 10,
    "api_status_url": "http://localhost:7000/api/status",
    "tls_insecure": False,  # if you need to accept self-signed certs (not recommended)
}

STOP_EVENT = Event()


# ---------- Helpers ----------
def safe_int(val: Any, default: int) -> int:
    try:
        return int(val)
    except Exception:
        return default


def load_config() -> Dict[str, Any]:
    """
    Read config.yaml and return the mqtt config merged with defaults.
    Returns the mqtt dict only (not entire config).
    """
    if not CFG_PATH.exists():
        LOG.warning("Config not found at %s — creating default config with MQTT disabled", CFG_PATH)
        # create minimal default file (do not overwrite if path not writable)
        try:
            CFG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with CFG_PATH.open("w", encoding="utf-8") as f:
                yaml.safe_dump({"mqtt": DEFAULT_MQTT}, f, sort_keys=False)
        except Exception as e:
            LOG.warning("Failed to write default config: %s", e)

    try:
        with CFG_PATH.open("r", encoding="utf-8") as f:
            cfg_full = yaml.safe_load(f) or {}
    except Exception as e:
        LOG.error("Failed to read config file %s: %s", CFG_PATH, e)
        cfg_full = {}

    mqtt_cfg = dict(DEFAULT_MQTT)
    if isinstance(cfg_full.get("mqtt"), dict):
        mqtt_cfg.update(cfg_full.get("mqtt") or {})
    else:
        # old config style or missing mqtt block
        mqtt_cfg = dict(DEFAULT_MQTT)

    # sanitize types
    mqtt_cfg["port"] = safe_int(mqtt_cfg.get("port"), DEFAULT_MQTT["port"])
    mqtt_cfg["ws_port"] = safe_int(mqtt_cfg.get("ws_port"), DEFAULT_MQTT["ws_port"])
    mqtt_cfg["tls_port"] = safe_int(mqtt_cfg.get("tls_port"), DEFAULT_MQTT["tls_port"])
    mqtt_cfg["tls_ws_port"] = safe_int(mqtt_cfg.get("tls_ws_port"), DEFAULT_MQTT["tls_ws_port"])
    mqtt_cfg["interval_seconds"] = max(MIN_INTERVAL, safe_int(mqtt_cfg.get("interval_seconds"), DEFAULT_MQTT["interval_seconds"]))
    mqtt_cfg["qos"] = max(0, min(2, safe_int(mqtt_cfg.get("qos"), DEFAULT_MQTT["qos"])))
    mqtt_cfg["retain"] = bool(mqtt_cfg.get("retain", DEFAULT_MQTT["retain"]))
    mqtt_cfg["use_tls"] = bool(mqtt_cfg.get("use_tls", DEFAULT_MQTT["use_tls"]))
    mqtt_cfg["use_websocket"] = bool(mqtt_cfg.get("use_websocket", DEFAULT_MQTT["use_websocket"]))
    mqtt_cfg["tls_insecure"] = bool(mqtt_cfg.get("tls_insecure", DEFAULT_MQTT["tls_insecure"]))

    return mqtt_cfg


def now_ts() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ---------- MQTT Wrapper ----------
class MqttClient:
    def __init__(self, cfg: Dict[str, Any]):
        self.cfg = cfg
        self.client: Optional[mqtt.Client] = None
        self.connected = False
        self._build_client()

    def _build_client(self):
        c = self.cfg
        client_id = c.get("client_id") or f"mqttsvc-{int(time.time())}-{random.randint(1000,9999)}"
        transport = "websockets" if c.get("use_websocket") else "tcp"

        # To be maximally compatible, avoid using CallbackAPIVersion explicitly.
        try:
            self.client = mqtt.Client(client_id=client_id, transport=transport)
        except TypeError:
            # older paho may not accept transport keyword - fall back
            LOG.debug("mqtt.Client transport keyword not accepted; calling simple constructor")
            self.client = mqtt.Client(client_id=client_id)

        # authentication
        if c.get("username"):
            self.client.username_pw_set(c["username"], c.get("password"))

        # TLS
        if c.get("use_tls"):
            try:
                self.client.tls_set(cert_reqs=ssl.CERT_REQUIRED)
                self.client.tls_insecure_set(c.get("tls_insecure", False))
            except Exception as e:
                LOG.warning("Failed to configure TLS: %s", e)

        # callbacks — accept both v1 and v2 signatures using *args
        def on_connect(client, userdata, *args):
            # rc is usually the last positional argument (v1: rc, v2: rc or properties last)
            rc = None
            if len(args) >= 1 and isinstance(args[-1], int):
                rc = args[-1]
            else:
                # fallback - try to inspect typical v1 pattern
                try:
                    rc = args[0]
                except Exception:
                    rc = 1
            if rc == 0:
                self.connected = True
                LOG.info("MQTT connected to %s", c.get("host"))
            else:
                self.connected = False
                LOG.warning("MQTT connection failed with rc=%s", rc)

        def on_disconnect(client, userdata, rc, *extra):
            self.connected = False
            LOG.warning("MQTT disconnected (rc=%s)", rc)

        self.client.on_connect = on_connect
        self.client.on_disconnect = on_disconnect

    def connect(self, timeout: int = 10) -> bool:
        if not self.client:
            self._build_client()
        c = self.cfg
        host = c.get("host")
        port = c.get("tls_port") if c.get("use_tls") and not c.get("use_websocket") else c.get("port")
        if c.get("use_websocket"):
            port = c.get("tls_ws_port") if c.get("use_tls") else c.get("ws_port")
        try:
            LOG.debug("Connecting MQTT to %s:%s (ws=%s tls=%s)", host, port, c.get("use_websocket"), c.get("use_tls"))
            self.client.connect(host, int(port), keepalive=60)
            self.client.loop_start()
            # wait short time for connect
            t0 = time.time()
            while not self.connected and time.time() - t0 < timeout:
                time.sleep(0.1)
            return self.connected
        except Exception as e:
            LOG.error("MQTT connect error: %s", e)
            return False

    def disconnect(self):
        try:
            if self.client:
                self.client.loop_stop()
                self.client.disconnect()
        except Exception as e:
            LOG.debug("Error during MQTT disconnect: %s", e)
        finally:
            self.connected = False

    def publish(self, topic: str, payload: str, qos: int = 0, retain: bool = False) -> bool:
        if not self.client:
            LOG.debug("MQTT client not built; rebuilding")
            self._build_client()
        if not self.connected:
            ok = self.connect()
            if not ok:
                LOG.error("MQTT not connected; publish aborted")
                return False
        try:
            r = self.client.publish(topic, payload=payload, qos=qos, retain=retain)
            # wait for publish when possible
            try:
                if hasattr(r, "wait_for_publish"):
                    r.wait_for_publish()
            except Exception:
                pass
            return True
        except Exception as e:
            LOG.error("MQTT publish error: %s", e)
            return False


# ---------- Worker thread ----------
class MqttWorker(Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self._cfg_mtime = None
        self._cfg: Dict[str, Any] = load_config()
        self.mqtt_client = MqttClient(self._cfg)
        self._backoff_base = 2.0

    def reload_if_changed(self) -> None:
        try:
            mtime = CFG_PATH.stat().st_mtime
        except Exception:
            return
        if self._cfg_mtime is None or mtime != self._cfg_mtime:
            LOG.info("Config file changed; reloading")
            self._cfg_mtime = mtime
            self._cfg = load_config()
            # recreate client with new settings
            try:
                self.mqtt_client.disconnect()
            except Exception:
                pass
            self.mqtt_client = MqttClient(self._cfg)

    def run(self):
        LOG.info("MQTT worker started (hot-reload: %s)", CFG_PATH)
        retry_attempts = 0
        while not STOP_EVENT.is_set():
            try:
                self.reload_if_changed()
                cfg = self._cfg
                if not cfg.get("enabled", False):
                    # sleep and poll for config changes quickly
                    time.sleep(1.0)
                    continue

                interval = max(MIN_INTERVAL, safe_int(cfg.get("interval_seconds"), DEFAULT_MQTT["interval_seconds"]))
                api_url = cfg.get("api_status_url", DEFAULT_MQTT["api_status_url"])
                topic = cfg.get("topic", DEFAULT_MQTT["topic"])
                qos = safe_int(cfg.get("qos"), DEFAULT_MQTT["qos"])
                retain = bool(cfg.get("retain", False))

                LOG.debug("Polling API %s (interval=%s) to publish to %s", api_url, interval, topic)
                try:
                    r = requests.get(api_url, timeout=6)
                    if r.status_code == 200:
                        payload = r.text.strip()
                        if not payload:
                            LOG.warning("Empty response from API %s", api_url)
                        ok = self.mqtt_client.publish(topic, payload, qos=qos, retain=retain)
                        if ok:
                            LOG.info("Published status to '%s' (len=%d)", topic, len(payload))
                            retry_attempts = 0  # reset on success
                        else:
                            LOG.warning("Publish returned False — will retry later")
                            retry_attempts += 1
                    else:
                        LOG.warning("Status API returned HTTP %s", r.status_code)
                        retry_attempts += 1
                except Exception as e:
                    LOG.error("Failed to fetch status API: %s", e)
                    retry_attempts += 1

                # adaptive backoff if repeated failures (publish/connect)
                if retry_attempts > 0:
                    backoff = min(60, (self._backoff_base ** min(retry_attempts, 6))) + random.random()
                    LOG.debug("Encountered %d consecutive failures; sleeping backoff %.1fs", retry_attempts, backoff)
                    slept = 0.0
                    while slept < backoff and not STOP_EVENT.is_set():
                        time.sleep(1.0)
                        slept += 1.0
                        self.reload_if_changed()
                    # continue loop
                else:
                    # regular sleep with hot-reload checks every second
                    slept = 0.0
                    while slept < interval and not STOP_EVENT.is_set():
                        time.sleep(1.0)
                        slept += 1.0
                        self.reload_if_changed()

            except Exception as e:
                LOG.exception("Worker loop unexpected error: %s", e)
                # brief sleep to avoid tight crash loop
                time.sleep(2.0)

        # shutdown
        try:
            self.mqtt_client.disconnect()
        except Exception:
            pass
        LOG.info("MQTT worker exiting")


# ---------- Signal handling ----------
def _signal_handler(signum, frame):
    LOG.info("Received signal %s — shutting down", signum)
    STOP_EVENT.set()


signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


# ---------- Entrypoint ----------
def main():
    LOG.info("Starting mqtt_service (config=%s)", CFG_PATH)
    worker = MqttWorker()
    worker.start()
    try:
        while not STOP_EVENT.is_set():
            time.sleep(0.5)
    except KeyboardInterrupt:
        STOP_EVENT.set()
    LOG.info("Shutting down mqtt_service...")
    worker.join(timeout=5.0)
    LOG.info("mqtt_service stopped")


if __name__ == "__main__":
    main()
