# mic_module.py
import numpy as np
import sounddevice as sd


def test_microphone():
    print("\n=== MICROPHONE TEST ===")
    try:
        duration = 5
        sample_rate = 44100
        print("Recording for 5 seconds...")
        recording = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype='int16')
        sd.wait()
        np.save("test_audio.npy", recording)
        print("[OK] Audio recorded and saved as test_audio.npy")
        return True
    except Exception as e:
        print("[ERROR] Microphone test failed:", e)
        return False


def get_sound(duration=1, sample_rate=44100):
    try:
        recording = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype='int16')
        sd.wait()
        return recording
    except:
        return None
