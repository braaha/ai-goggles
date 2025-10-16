import os
import time
import numpy as np
import sounddevice as sd
from datetime import datetime

# Trying camera
try:
    from picamera2 import Picamera2
    CAMERA_AVAILABLE = True
except ImportError:
    CAMERA_AVAILABLE = False

import cv2

# Settings
w = 1280
h = 720
fps = 15
rate = 44100


def test_camera():
    print("camera test")
    if not CAMERA_AVAILABLE:
        print("[ERROR] Picamera2 not available on this system.")
        return False

    try:
        picam2 = Picamera2()
        picam2.start()
        time.sleep(2)
        #saving as year,month,day,hour,minutes,time
        filename = f"test_image_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        picam2.capture_file(filename)
        picam2.close()
        print(f"OK: Image captured and saved as {filename}")
        return True
    except Exception as e:
        print("ERROR: Camera test failed:", e)
        return False


def test_microphone():
    print("MICROPHONE TEST")
    try:
        duration = 5
        sample_rate = 44100
        print("recording for 5 seconds")
        recording = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype='int16')
        sd.wait()
        np.save("test_audio.npy", recording)
        print("OK: Audio recorded and saved as test_audio.npy")
        return True
    except Exception as e:
        print("ERROR: Microphone test failed:", e)
        return False


def get_frame():
    if CAMERA_AVAILABLE:
        try:
            picam2 = Picamera2()
            picam2.start()
            frame = picam2.capture_array()
            picam2.close()
            return frame
        except:
            frame = np.zeros((h, w, 3), dtype=np.uint8)
            return frame
    else:
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        return frame


def analyze_frame(frame, mode="edges"):
    if frame is None:
        return None
    
    if mode == "edges":
        edges = cv2.Canny(frame, 100, 200)
        edges_colored = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
        return edges_colored
    else:
        return frame


def run_simulation():
    print("STARTING SIMULATION")
    frames = 0
    t0 = time.time()
    try:
        while frames < 50:
            frame = get_frame()
            analyzed = analyze_frame(frame, "edges")
            frames += 1
            if frames % 10 == 0:
                print(f"Captured {frames} frames...")
            time.sleep(1.0 / fps)
    except KeyboardInterrupt:
        print("Stopped manually")
    finally:
        dt = time.time() - t0
        if dt <= 0:
            dt = 1
        print("Average FPS:", round(frames / dt, 2))
        
        print("Simulation complete.")


if __name__ == "__main__":
    print("AI GOGGLES TEST START:  ")
    cam_ok = test_camera()
    mic_ok = test_microphone()
    if cam_ok and mic_ok:
        print("Both camera and microphone are working")
    else:
        print("One or more tests fail")

    run_simulation()
