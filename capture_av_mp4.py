# MP4 file (no AWS).

import argparse
import subprocess
import threading
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


def record_audio_async(
    out_buffer: dict,
    key: str,
    seconds: int,
    samplerate: int,
    channels: int,
) -> None:

    frames = int(seconds * samplerate)
    buf = sd.rec(frames, samplerate=samplerate, channels=channels, dtype="int16")
    sd.wait()
    out_buffer[key] = buf


def make_mp4(video_path: Path, audio_path: Path, output_path: Path) -> None:

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-i",
        str(audio_path),
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-shortest",
        str(output_path),
    ]
    print("Running:", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("ffmpeg failed:")
        print(result.stderr)
    else:
        print("Created MP4:", output_path.resolve())


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Record Pi camera video + mic audio and make MP4 (no AWS)."
    )
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
    final_path = Path(f"final_{ts}.mp4")


    audio_store: dict[str, np.ndarray] = {}


    audio_thread = threading.Thread(
        target=record_audio_async,
        args=(audio_store, "buf", args.seconds, args.samplerate, args.channels),
        daemon=True,
    )
    audio_thread.start()


    record_video(video_path, args.seconds, args.width, args.height, args.bitrate)


    audio_thread.join()

    audio_buf = audio_store.get("buf")
    if audio_buf is None:
        print("No audio buffer recorded, skipping WAV/MP4 creation.")
        return

    sf.write(str(audio_path), audio_buf, args.samplerate)

    print(f"Saved video: {video_path.resolve()}")
    print(f"Saved audio: {audio_path.resolve()}")

    # make MP4
    make_mp4(video_path, audio_path, final_path)


if __name__ == "__main__":
    main()
