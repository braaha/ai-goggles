"""
capture_av.py
Record Pi camera video and mic audio.
"""

import argparse
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf
from picamera2 import Picamera2, encoders


def record_video(path: Path, seconds: int, width: int, height: int, bitrate: int) -> None:
    picam2 = Picamera2()
    config = picam2.create_video_configuration(main={"size": (width, height)})
    picam2.configure(config)
    encoder = encoders.H264Encoder(bitrate=bitrate)
    picam2.start_recording(encoder, str(path))
    try:
        time.sleep(seconds)
    finally:
        picam2.stop_recording()
        picam2.close()


def record_audio(seconds: int, samplerate: int, channels: int) -> np.ndarray:
    frames = int(seconds * samplerate)
    buf = sd.rec(frames, samplerate=samplerate, channels=channels, dtype="int16")
    sd.wait()
    return buf


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Record Pi camera video and mic audio.")
    ap.add_argument("--seconds", type=int, default=10)
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    ap.add_argument("--samplerate", type=int, default=48000)
    ap.add_argument("--channels", type=int, default=1)
    ap.add_argument("--bitrate", type=int, default=10_000_000)
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    video_path = Path(f"video_{ts}.h264")
    audio_path = Path(f"audio_{ts}.wav")

    audio_frames = record_audio(args.seconds, args.samplerate, args.channels)
    record_video(video_path, args.seconds, args.width, args.height, args.bitrate)
    sf.write(str(audio_path), audio_frames, args.samplerate)

    print(f"Saved: {video_path.resolve()}")
    print(f"Saved: {audio_path.resolve()}")


if __name__ == "__main__":
    main()
