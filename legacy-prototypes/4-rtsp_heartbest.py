import cv2
import csv
import time
from datetime import datetime
import threading

# --- CONFIGURATION ---
cameras = {
    "D1": {"ip": "10.1.40.34", "rtsp": "rtsp://admin:abcde@12@10.1.40.34:554/Streaming/channels/102", "note": "Wiring issue"},
    "D2": {"ip": "10.1.40.35", "rtsp": "rtsp://admin:abcde@12@10.1.40.35:554/Streaming/channels/102", "note": ""},
    "D3": {"ip": "10.1.40.36", "rtsp": "rtsp://admin:abcde@12@10.1.40.36:554/Streaming/channels/102", "note": ""},
    "D4": {"ip": "10.1.40.37", "rtsp": "rtsp://admin:abcde@12@10.1.40.37:554/Streaming/channels/102", "note": ""},
    "D5": {"ip": "10.1.40.38", "rtsp": "rtsp://admin:abcde@12@10.1.40.38:554/Streaming/channels/102", "note": ""},
    "D6": {"ip": "10.1.40.39", "rtsp": "rtsp://admin:abcde@12@10.1.40.39:554/Streaming/channels/102", "note": "Wiring issue"},
    "D7": {"ip": "10.1.40.40", "rtsp": "rtsp://admin:abcde@12@10.1.40.40:554/Streaming/channels/102", "note": ""},
    "D8": {"ip": "10.1.40.41", "rtsp": "rtsp://admin:abcde@12@10.1.40.41:554/Streaming/channels/102", "note": "Wiring issue"},
    "D9": {"ip": "10.1.40.42", "rtsp": "rtsp://admin:abcde@12@10.1.40.42:554/Streaming/channels/102", "note": "Wiring issue"}
}

network_label = "IoT-LAB"
test_duration = 30  # seconds for sample test
fetch_interval = 10
retry_attempts = 2

lock = threading.Lock()  # Thread-safe CSV writing

# --- FUNCTIONS ---
def log_result(device, ip, rtsp_url, status, latency_ms, note):
    filename = f"{device}_rtsp_log.csv"
    with lock:
        with open(filename, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), device, ip, rtsp_url, network_label, status, latency_ms, note])

def test_camera(device, ip, rtsp_url, note):
    start = time.time()
    cap = cv2.VideoCapture(rtsp_url)
    frame_received = False

    if not cap.isOpened():
        for _ in range(retry_attempts):
            cap.release()
            time.sleep(1)
            cap = cv2.VideoCapture(rtsp_url)
            if cap.isOpened():
                break

    if cap.isOpened():
        ret, frame = cap.read()
        if ret:
            frame_received = True
    cap.release()
    latency_ms = int((time.time() - start) * 1000)
    return "Frame Received" if frame_received else "Frame Not Received", latency_ms

def camera_thread(device, info):
    status, latency = test_camera(device, info["ip"], info["rtsp"], info["note"])
    log_result(device, info["ip"], info["rtsp"], status, latency, info["note"])
    print(f"{datetime.now()} | {device} | {status} | Latency: {latency} ms | Note: {info['note']}")

# Initialize CSV files with header
for device in cameras:
    with open(f"{device}_rtsp_log.csv", 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "device", "ip", "rtsp_url", "network", "status", "frame_latency_ms", "note"])

# --- RUN TEST ---
print(f"Starting parallel RTSP audit for {network_label} ({test_duration} sec)...")
start_time = time.time()
while time.time() - start_time < test_duration:
    threads = []
    for device, info in cameras.items():
        t = threading.Thread(target=camera_thread, args=(device, info))
        t.start()
        threads.append(t)
    for t in threads:
        t.join()
    time.sleep(fetch_interval)

print("Parallel RTSP audit completed. Individual CSV logs generated for each camera.")
