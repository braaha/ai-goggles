import os
import time
import numpy as np
import sounddevice as sd
from datetime import datetime

print("CAMERA tEST:")
try:
    from picamera2 import Picamera2
    picam2 = Picamera2()
    picam2.start()
    time.sleep(2)
    filename = f"test_image_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
    picam2.capture_file(filename)
    picam2.close()
    
    print(f"OK thee video is workin and saved as {filename}")
except Exception as e:
    print("[ERROR] Camera test failed:", e)

print("MICROPHONE TEST: ")
try:
    duration = 5
    sample_rate = 44100
    print("recording for 5 secs")
    recording = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype='int16')
    sd.wait()
    np.save("test_audio.npy", recording)
    print("OK: Audio recorded and saved as test_audio.npy")
    
except Exception:
    print("[ERROR] Microphone test failed:")

print("TEST COMPLETE")
#2 ok means both work
