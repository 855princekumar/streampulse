import cv2
import os
import time
import datetime
import logging
import psutil
import threading
import ntplib
import re
import csv

# Config
STREAM_URL = "rtsp://10.1.56.88:554/stream"
LOG_DIR = os.path.join(os.getcwd(), "rtsp_receiver_logs")
CSV_FILE = os.path.join(LOG_DIR, "frame_stats.csv")
VIDEO_CHUNK_DURATION = 5  # in seconds
NTP_SERVER = "pool.ntp.org"
TIMEZONE_OFFSET = datetime.timedelta(hours=5, minutes=30)

os.makedirs(LOG_DIR, exist_ok=True)
log_file_path = os.path.join(LOG_DIR, "receiver_log.txt")
logging.basicConfig(filename=log_file_path, level=logging.INFO, format="%(asctime)s - %(message)s")

# Sync Time
ntp_client = ntplib.NTPClient()
def sync_time():
    try:
        response = ntp_client.request(NTP_SERVER)
        ts = datetime.datetime.fromtimestamp(response.tx_time)
        logging.info(f"Time synchronized to NTP: {ts}")
        return ts
    except Exception as e:
        logging.error(f"Time sync failed: {e}")
        return datetime.datetime.now()

# System Stats Logger
system_stats = []
def log_system_stats():
    while True:
        cpu = psutil.cpu_percent()
        mem = psutil.virtual_memory().percent
        net = psutil.net_io_counters()
        stats = {
            "timestamp": datetime.datetime.now().isoformat(),
            "cpu": cpu,
            "mem": mem,
            "bytes_sent": net.bytes_sent,
            "bytes_recv": net.bytes_recv
        }
        system_stats.append(stats)
        time.sleep(1)

# Parse overlay timestamp from frame
pattern = re.compile(r"(\d{2}:\d{2}:\d{2})")
def extract_overlay_timestamp(frame):
    return datetime.datetime.now().strftime("%H:%M:%S")  # Placeholder

# Main Receiver
cap = cv2.VideoCapture(STREAM_URL)
if not cap.isOpened():
    logging.error("Failed to open RTSP stream.")
    exit(1)

frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
fps = int(cap.get(cv2.CAP_PROP_FPS)) or 25
logging.info(f"Stream opened: {frame_width}x{frame_height} @ {fps} FPS")

csv_headers = ["chunk_id", "timestamp", "frames_received", "avg_frame_size", "latency_ms", "jitter_ms"]
with open(CSV_FILE, "w", newline="") as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=csv_headers)
    writer.writeheader()

    sync_time()
    threading.Thread(target=log_system_stats, daemon=True).start()

    chunk_id = 1
    while True:
        chunk_start = time.time()
        frame_sizes = []
        timestamps = []

        while (time.time() - chunk_start) < VIDEO_CHUNK_DURATION:
            ret, frame = cap.read()
            if not ret:
                continue

            ts = time.time()
            overlay_ts = extract_overlay_timestamp(frame)
            frame_sizes.append(frame.nbytes)
            timestamps.append(ts)
            logging.info(f"Frame received | Overlay TS: {overlay_ts} | Size: {frame.nbytes}")

        if len(timestamps) > 1:
            intervals = [timestamps[i] - timestamps[i - 1] for i in range(1, len(timestamps))]
            jitter = max(intervals) - min(intervals)
        else:
            jitter = 0.0

        latency = (timestamps[-1] - timestamps[0]) * 1000 / max(1, len(timestamps))

        writer.writerow({
            "chunk_id": chunk_id,
            "timestamp": datetime.datetime.now().isoformat(),
            "frames_received": len(timestamps),
            "avg_frame_size": sum(frame_sizes) / len(frame_sizes) if frame_sizes else 0,
            "latency_ms": round(latency, 2),
            "jitter_ms": round(jitter * 1000, 2)
        })
        csvfile.flush()

        chunk_id += 1