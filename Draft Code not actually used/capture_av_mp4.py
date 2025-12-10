#!/usr/bin/env python3


import argparse
import subprocess
import time
from datetime import datetime
from pathlib import Path

from picamera2 import Picamera2, encoders


def record_video(path: Path, seconds: int, width: int, height: int,
                 fps: int, bitrate: int) -> None:
    """Record raw H.264 video from the Pi camera to `path`."""
    picam2 = Picamera2()

    config = picam2.create_video_configuration(
        main={"size": (width, height)}
    )
    picam2.configure(config)

    encoder = encoders.H264Encoder(bitrate=bitrate)

    print(f"Starting video recording to: {path}")
    picam2.start_recording(encoder, str(path))
    try:
        time.sleep(seconds)
    finally:
        picam2.stop_recording()
        picam2.close()
    print(f"Finished video recording: {path}")


def record_audio_arecord(path: Path, seconds: int, samplerate: int,
                         channels: int, device: str) -> None:

    cmd = [
        "arecord",
        "-D", device,
        "-f", "S16_LE",
        "-r", str(samplerate),
        "-c", str(channels),
        "-d", str(seconds),
        str(path),
    ]
    print("Running audio command:", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("arecord failed:")
        print(result.stderr)
        raise RuntimeError("arecord failed")
    print(f"Audio recorded to: {path}")


def make_mp4(video_path: Path, audio_path: Path, output_path: Path,
             fps: int) -> None:
    """
    Merge raw H.264 + WAV into MP4.

    We reencode the video with libx264 so that timestamps are correct
    and the audio track is kept.
    """
    cmd = [
        "ffmpeg",
        "-y",
        "-r", str(fps),             # frame rate for raw H.264 input
        "-i", str(video_path),
        "-i", str(audio_path),
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "128k",
        "-shortest",
        str(output_path),
    ]
    print("Running:", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("ffmpeg failed:")
        print(result.stderr)
        raise RuntimeError("ffmpeg merge failed")

    print(f"MP4 created: {output_path.resolve()}")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Record Pi camera video + Google Voice HAT audio into an MP4."
    )
    ap.add_argument("--seconds", type=int, default=5,
                    help="Recording length in seconds.")
    ap.add_argument("--width", type=int, default=1280,
                    help="Video width.")
    ap.add_argument("--height", type=int, default=720,
                    help="Video height.")
    ap.add_argument("--fps", type=int, default=30,
                    help="Assumed video frame rate.")
    ap.add_argument("--samplerate", type=int, default=44100,
                    help="Audio sample rate.")
    ap.add_argument("--channels", type=int, default=2,
                    help="Number of audio channels.")
    ap.add_argument("--bitrate", type=int, default=10_000_000,
                    help="Video bitrate for H.264 encoder.")
    ap.add_argument(
        "--audio-device",
        type=str,
        default="plughw:1,0",
        help='ALSA audio device for arecord (for Google Voice HAT use "plughw:1,0").',
    )
    return ap.parse_args()


def main() -> None:
    args = parse_args()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    video_path = Path(f"video_{ts}.h264")
    audio_path = Path(f"audio_{ts}.wav")
    final_path = Path(f"final_{ts}.mp4")

    # Record audio and video one after another.
    # If you want them closer in time, you can start audio first,
    # then immediately start video in another thread.
    record_audio_arecord(
        audio_path,
        seconds=args.seconds,
        samplerate=args.samplerate,
        channels=args.channels,
        device=args.audio_device,
    )

    record_video(
        video_path,
        seconds=args.seconds,
        width=args.width,
        height=args.height,
        fps=args.fps,
        bitrate=args.bitrate,
    )

    print(f"Saved video: {video_path.resolve()}")
    print(f"Saved audio: {audio_path.resolve()}")

    make_mp4(video_path, audio_path, final_path, fps=args.fps)

    print("DONE")
    print(f"Video file: {video_path.name}")
    print(f"Audio file: {audio_path.name}")
    print(f"Final MP4: {final_path.name}")


if __name__ == "__main__":
    main()
