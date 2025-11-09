import subprocess
import datetime
import threading
import time
import os
import psutil
import ntplib
import logging

# Config
STREAM_FPS = 25
RESOLUTION = "640x480"
BITRATE = "1M"
STREAM_URL = "rtsp://10.1.59.128:554/stream"
VIDEO_DEVICE = "/dev/video0"
LOG_DIR = os.path.join(os.getcwd(), "rtsp_sender_logs")
NTP_SERVER = "pool.ntp.org"

os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "sender_log.txt")
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s - %(message)s")

# Sync time
ntp_client = ntplib.NTPClient()
def sync_time():
    try:
        response = ntp_client.request(NTP_SERVER)
        ts = datetime.datetime.fromtimestamp(response.tx_time)
        logging.info(f"NTP synced: {ts}")
    except Exception as e:
        logging.warning(f"NTP sync failed: {e}")

# System stats logger
def log_system_stats():
    while True:
        cpu = psutil.cpu_percent()
        mem = psutil.virtual_memory().percent
        net = psutil.net_io_counters()
        logging.info(f"CPU: {cpu}% | MEM: {mem}% | Bytes Sent: {net.bytes_sent} | Bytes Received: {net.bytes_recv}")
        time.sleep(1)

# Streaming process using FFmpeg
def start_stream():
    ffmpeg_cmd = [
        "ffmpeg",
        "-f", "v4l2",
        "-framerate", str(STREAM_FPS),
        "-video_size", RESOLUTION,
        "-i", VIDEO_DEVICE,
        "-vf", "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:text='%{eif\\:n+1\\:d}:%{pts\\:hms}':x=10:y=10:fontsize=12:fontcolor=white:box=1",
        "-c:v", "h264_omx",
        "-b:v", BITRATE,
        "-f", "rtsp",
        STREAM_URL
    ]
    logging.info("Starting FFmpeg stream with overlay")
    process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    process.wait()

if __name__ == '__main__':
    sync_time()
    threading.Thread(target=log_system_stats, daemon=True).start()
    start_stream()