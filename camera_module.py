# camera_module.py
import time
from datetime import datetime
import numpy as np

try:
    from picamera2 import Picamera2
    CAMERA_AVAILABLE = True
except ImportError:
    CAMERA_AVAILABLE = False


def test_camera():
    print("=== CAMERA TEST ===")
    if not CAMERA_AVAILABLE:
        print("[ERROR] Picamera2 not available.")
        return False

    try:
        picam2 = Picamera2()
        picam2.start()
        time.sleep(2)
        filename = f"test_image_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        picam2.capture_file(filename)
        picam2.close()
        print(f"[OK] Image saved as {filename}")
        return True
    except Exception as e:
        print("[ERROR] Camera test failed:", e)
        return False


def get_frame(width=1280, height=720):
    if CAMERA_AVAILABLE:
        try:
            picam2 = Picamera2()
            picam2.start()
            frame = picam2.capture_array()
            picam2.close()
            return frame
        except Exception:
            return np.zeros((height, width, 3), dtype=np.uint8)
    else:
        return np.zeros((height, width, 3), dtype=np.uint8)
