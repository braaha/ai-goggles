#!/usr/bin/env python3


import argparse
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

from picamera2 import Picamera2, encoders


def record_video(
    path: Path,
    seconds: int,
    width: int,
    height: int,
    bitrate: int,
    fps: int,
) -> None:
 

    picam2 = Picamera2()

    config = picam2.create_video_configuration(
        main={"size": (width, height)},
        controls={"FrameDurationLimits": (int(1e6 / fps), int(1e6 / fps))},
    )
    picam2.configure(config)

    encoder = encoders.H264Encoder(bitrate=bitrate)

    print(f"[VIDEO] Starting recording to {path} ({width}x{height}, {fps} fps)")
    picam2.start_recording(encoder, str(path))

    try:
        time.sleep(seconds)
    finally:
        print("[VIDEO] Stopping recording")
        picam2.stop_recording()
        picam2.close()


def record_audio_arecord(
    path: Path,
    seconds: int,
    samplerate: int,
    channels: int,
    device: str,
) -> None:


    cmd = [
        "arecord",
        "-D",
        device,
        "-f",
        "S16_LE",
        "-r",
        str(samplerate),
        "-c",
        str(channels),
        "-d",
        str(seconds),
        str(path),
    ]

    print("[AUDIO] Running audio command:", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print("[AUDIO] arecord FAILED")
        print(result.stderr)
        raise RuntimeError("arecord failed")

    print(f"[AUDIO] Audio recorded to: {path}")


def make_mp4(
    video_path: Path,
    audio_path: Path,
    output_path: Path,
    fps: int,
) -> None:


    cmd = [
        "ffmpeg",
        "-y",
        "-r",
        str(fps),              # input frame rate hint for raw H.264
        "-i",
        str(video_path),
        "-i",
        str(audio_path),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-c:a",
        "aac",
        "-shortest",
        str(output_path),
    ]

    print("[FFMPEG] Running:", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print("[FFMPEG] ffmpeg FAILED")
        print(result.stderr)
        raise RuntimeError("ffmpeg failed")

    print(f"[FFMPEG] MP4 created: {output_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Record Pi camera video + Google Voice HAT audio into an MP4."
    )
    parser.add_argument("--seconds", type=int, default=5, help="Recording length in seconds")
    parser.add_argument("--width", type=int, default=1280, help="Video width")
    parser.add_argument("--height", type=int, default=720, help="Video height")
    parser.add_argument("--bitrate", type=int, default=10_000_000, help="Video bitrate (bits per second)")
    parser.add_argument("--samplerate", type=int, default=44100, help="Audio sample rate")
    parser.add_argument("--channels", type=int, default=2, help="Audio channels (2 = stereo)")
    parser.add_argument("--fps", type=int, default=30, help="Video frames per second")
    parser.add_argument(
        "--arecord-device",
        type=str,
        default="plughw:1,0",
        help="ALSA device string for arecord (e.g., plughw:1,0 for Google Voice HAT)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    video_path = Path(f"video_{ts}.h264")
    audio_path = Path(f"audio_{ts}.wav")
    final_path = Path(f"final_{ts}.mp4")

    print("==========================================")
    print(" Starting capture")
    print(f"  Seconds:     {args.seconds}")
    print(f"  Resolution:  {args.width}x{args.height}")
    print(f"  FPS:         {args.fps}")
    print(f"  Audio rate:  {args.samplerate} Hz")
    print(f"  Audio ch:    {args.channels}")
    print(f"  Device:      {args.arecord_device}")
    print("==========================================")

    # Run audio and video in parallel so they overlap
    audio_thread = threading.Thread(
        target=record_audio_arecord,
        args=(
            audio_path,
            args.seconds,
            args.samplerate,
            args.channels,
            args.arecord_device,
        ),
        daemon=True,
    )

    audio_thread.start()
    record_video(
        video_path,
        args.seconds,
        args.width,
        args.height,
        args.bitrate,
        args.fps,
    )
    audio_thread.join()

    # Sanity check: files must exist
    if not audio_path.exists():
        print("[ERROR] Audio file was not created. Aborting.")
        return
    if not video_path.exists():
        print("[ERROR] Video file was not created. Aborting.")
        return

    print(f"[INFO] Saved video: {video_path.resolve()}")
    print(f"[INFO] Saved audio: {audio_path.resolve()}")

    # Make MP4
    make_mp4(video_path, audio_path, final_path, args.fps)

    print("==========================================")
    print(" DONE")
    print(f" Video file: {video_path.name}")
    print(f" Audio file: {audio_path.name}")
    print(f" Final MP4:  {final_path.name}")
    print("==========================================")


if __name__ == "__main__":
    main()
