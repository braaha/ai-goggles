import os
import time
import numpy as np
import sounddevice as sd
import cv2
from datetime import datetime

# Try importing the camera library
try:
    from picamera2 import Picamera2
    CAMERA_AVAILABLE = True
except ImportError:
    CAMERA_AVAILABLE = False


# ====== SETTINGS ======
WIDTH = 1280
HEIGHT = 720
FPS = 15
AUDIO_RATE = 44100
AUDIO_DURATION = 5
SAVE_DIR = "ai_goggles_tests"

# Create save folder if it doesn’t exist
os.makedirs(SAVE_DIR, exist_ok=True)


# ====== CAMERA TEST ======
def test_camera():
    print("\n=== CAMERA TEST ===")
    if not CAMERA_AVAILABLE:
        print("[ERROR] Picamera2 not installed or camera not found.")
        return False

    try:
        picam2 = Picamera2()
        picam2.start()
        time.sleep(2)

        filename = os.path.join(
            SAVE_DIR,
            f"camera_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        )
        picam2.capture_file(filename)
        picam2.close()

        if os.path.exists(filename):
            print(f"[OK] Image captured and saved as {filename}")
            return True
        else:
            print("[ERROR] File not saved correctly.")
            return False

    except Exception as e:
        print("[ERROR] Camera test failed:", e)
        return False


# ====== MICROPHONE TEST ======
def test_microphone():
    print("\n=== MICROPHONE TEST ===")
    try:
        print(f"Recording {AUDIO_DURATION} seconds of audio...")
        recording = sd.rec(
            int(AUDIO_DURATION * AUDIO_RATE),
            samplerate=AUDIO_RATE,
            channels=1,
            dtype='int16'
        )
        sd.wait()

        filename = os.path.join(
            SAVE_DIR,
            f"audio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.npy"
        )
        np.save(filename, recording)

        # Basic “did we capture sound” check
        amplitude = np.abs(recording).mean()
        if amplitude < 10:
            print("[WARNING] Mic recorded almost silence. Check mic connection.")
        else:
            print(f"[OK] Audio recorded (avg volume: {amplitude:.1f}) and saved as {filename}")

        return True
    except Exception as e:
        print("[ERROR] Microphone test failed:", e)
        return False


# ====== VIDEO SIMULATION TEST ======
def get_frame():
    if CAMERA_AVAILABLE:
        try:
            picam2 = Picamera2()
            picam2.start()
            frame = picam2.capture_array()
            picam2.close()
            return frame
        except:
            return np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
    else:
        return np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)


def analyze_frame(frame):
    if frame is None:
        return None
    edges = cv2.Canny(frame, 100, 200)
    return cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)


def run_simulation():
    print("\n=== SIMULATION ===")
    frames = 0
    t0 = time.time()

    try:
        while frames < 30:
            frame = get_frame()
            processed = analyze_frame(frame)
            frames += 1
            if frames % 10 == 0:
                print(f"Processed {frames} frames...")
            time.sleep(1.0 / FPS)
    except KeyboardInterrupt:
        print("Stopped manually.")
    finally:
        elapsed = time.time() - t0
        print(f"Average FPS: {frames / elapsed:.2f}")
        print("Simulation complete.")


# ====== MAIN PROGRAM ======
if __name__ == "__main__":
    print("=== AI GOGGLES SYSTEM TEST START ===")

    cam_ok = test_camera()
    mic_ok = test_microphone()

    if cam_ok and mic_ok:
        print("\nBoth camera and microphone are working correctly.")
    else:
        print("\nOne or more devices failed. Please check wiring or connections.")

    run_simulation()
