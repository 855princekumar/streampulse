import sys
import time
import platform
from datetime import datetime

# -------------------- Check Modules --------------------
missing = []

try:
    import cv2
except ImportError:
    missing.append("opencv-python")

try:
    import mysql.connector
except ImportError:
    missing.append("mysql-connector-python")

if missing:
    print(f"\n[❌ ERROR] Required modules missing: {', '.join(missing)}")
    print("Please install them manually with:\n")
    print(f"  pip install {' '.join(missing)}\n")
    print("If you are offline, try:\n")
    print("  sudo apt install python3-opencv\n  OR manually use wheel files for offline install.\n")
    sys.exit(1)

# -------------------- DB Config --------------------
DB_HOST = "localhost"
DB_USER = "admin"
DB_PASSWORD = "admin"
DB_NAME = "rtsp_logs"
TABLE_NAME = "camera_logs"

CAMERA_IPS = [
    "10.1.40.34", "10.1.40.35", "10.1.40.36",
    "10.1.40.37", "10.1.40.38", "10.1.40.39",
    "10.1.40.40", "10.1.40.41", "10.1.40.42"
]

RTSP_CREDENTIALS = [
    ("rtsp_user", "rtspUser123"),
    ("admin", "admin123")
]

import cv2
import mysql.connector
import subprocess

# -------------------- DB Setup --------------------
def init_db():
    conn = mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
    conn.database = DB_NAME
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            id INT AUTO_INCREMENT PRIMARY KEY,
            timestamp DATETIME NOT NULL,
            camera_ip VARCHAR(64) NOT NULL,
            ping_status BOOLEAN NOT NULL,
            rtsp_status BOOLEAN NOT NULL
        )
    """)
    conn.commit()
    return conn

# -------------------- Utilities --------------------
def ping_host(ip):
    if platform.system().lower() == "windows":
        cmd = ["ping", "-n", "1", "-w", "1000", ip]
    else:
        cmd = ["ping", "-c", "1", "-W", "1", ip]
    return subprocess.call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0

def check_rtsp_opencv(ip):
    for user, password in RTSP_CREDENTIALS:
        rtsp_url = f"rtsp://{user}:{password}@{ip}:554/Streaming/channels/102"
        try:
            cap = cv2.VideoCapture(rtsp_url)
            if not cap.isOpened():
                continue
            ret, frame = cap.read()
            cap.release()
            if ret and frame is not None:
                return True
        except Exception:
            continue
    return False

def log_entry(cursor, timestamp, ip, ping, rtsp):
    cursor.execute(f"""
        INSERT INTO {TABLE_NAME} (timestamp, camera_ip, ping_status, rtsp_status)
        VALUES (%s, %s, %s, %s)
    """, (timestamp, ip, ping, rtsp))

# -------------------- Main Logic --------------------
def main():
    conn = init_db()
    cursor = conn.cursor()

    while True:
        now = datetime.now()
        for ip in CAMERA_IPS:
            ping_result = ping_host(ip)
            rtsp_result = check_rtsp_opencv(ip) if ping_result else False
            log_entry(cursor, now, ip, ping_result, rtsp_result)
            print(f"[{now}] {ip} | PING: {ping_result} | RTSP: {rtsp_result}")
        conn.commit()
        time.sleep(5)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:

        print("Monitoring stopped.")
