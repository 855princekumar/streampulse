# ===============================
# MOTIONEYE STREAM RECEIVER SCRIPT (ONLY RECEIVER)
# ===============================

import cv2
import os
import time
import datetime
import logging
import psutil
import ntplib
import threading
import shutil

# Configuration
STREAM_URL = "http://192.168.1.1:9081"  # MotionEye HTTP stream URL
LOG_FOLDER = os.path.join(os.getcwd(), "motioneye_receiver")
VIDEO_CHUNK_DURATION = 5  # in seconds
NTP_SERVER = "pool.ntp.org"
TIMEZONE_OFFSET = datetime.timedelta(hours=5, minutes=30)  # IST

# Setup Directories
os.makedirs(LOG_FOLDER, exist_ok=True)
VIDEO_FOLDER = os.path.join(LOG_FOLDER, "video_chunks")
os.makedirs(VIDEO_FOLDER, exist_ok=True)

# Logging Setup
log_file_path = os.path.join(LOG_FOLDER, "receiver_log.txt")
logging.basicConfig(filename=log_file_path, level=logging.INFO, format="%(asctime)s - %(message)s")

# Time Sync Function
def sync_time():
    try:
        client = ntplib.NTPClient()
        response = client.request(NTP_SERVER)
        current_time = datetime.datetime.fromtimestamp(response.tx_time) + TIMEZONE_OFFSET
        logging.info(f"Time synchronized to NTP: {current_time.isoformat()}")
        return current_time
    except Exception as e:
        logging.error(f"Time sync failed: {e}")
        return datetime.datetime.now() + TIMEZONE_OFFSET

# System Stats Logger
def log_system_stats():
    while True:
        cpu = psutil.cpu_percent()
        mem = psutil.virtual_memory().percent
        net = psutil.net_io_counters()
        logging.info(f"CPU: {cpu}% | MEM: {mem}% | Bytes Sent: {net.bytes_sent} | Bytes Received: {net.bytes_recv}")
        time.sleep(1)

# Main Stream Processing

def receive_stream():
    cap = cv2.VideoCapture(STREAM_URL)
    if not cap.isOpened():
        logging.error("Failed to open stream.")
        return

    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = int(cap.get(cv2.CAP_PROP_FPS)) or 25

    logging.info(f"Stream opened | Resolution: {frame_width}x{frame_height} | FPS: {fps}")

    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    current_chunk = 1
    synced_time = sync_time()

    while True:
        chunk_start = time.time()
        chunk_name = f"chunk_{current_chunk}_{synced_time.strftime('%Y%m%d_%H%M%S')}.avi"
        video_path = os.path.join(VIDEO_FOLDER, chunk_name)
        out = cv2.VideoWriter(video_path, fourcc, fps, (frame_width, frame_height))

        while (time.time() - chunk_start) < VIDEO_CHUNK_DURATION:
            ret, frame = cap.read()
            if not ret:
                logging.warning("Failed to grab frame.")
                continue

            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
            cv2.putText(frame, f"Timestamp: {timestamp}", (10, frame.shape[0] - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
            out.write(frame)
            logging.info(f"Frame received | Timestamp: {timestamp} | Size: {frame.nbytes} bytes")

        out.release()

        # Cross-verify and delete older chunk
        if current_chunk > 1:
            old_chunk = os.path.join(VIDEO_FOLDER, f"chunk_{current_chunk - 1}_{synced_time.strftime('%Y%m%d_%H%M%S')}.avi")
            if os.path.exists(old_chunk):
                try:
                    os.remove(old_chunk)
                    logging.info(f"Deleted old chunk: {old_chunk}")
                except Exception as e:
                    logging.warning(f"Failed to delete old chunk: {e}")

        current_chunk += 1

if __name__ == '__main__':
    sync_time()
    stats_thread = threading.Thread(target=log_system_stats, daemon=True)
    stats_thread.start()
    receive_stream()

