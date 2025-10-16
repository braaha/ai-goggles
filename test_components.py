import time
import numpy as np
import sounddevice as sd
from datetime import datetime

print("TEST Camera: ")
try:
    from picamera2 import Picamera2
    cam = Picamera2()
    cam.start()
    time.sleep(2)
    name = f"test_image_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
    cam.capture_file(name)
    cam.close()
    print(f"OK: Camera is working. Saved image as {name}")
except Exception as e:
    print("ERROR: Camera not detected or not working:", e)

print("\n=== MICROPHONE TEST ===")
try:
    print("Recording 3 seconds of audio...")
    record = sd.rec(int(3 * 44100), samplerate=44100, channels=1, dtype='int16')
    sd.wait()
    np.save("test_audio.npy", record)
    print("OK: Microphone is working. Saved as test_audio.npy")
except Exception as e:
    print("ERROR: Microphone not detected or not working:", e)

print("TEST COMPLETE.")
print("If you see both OK messages, everything works correctly.")
