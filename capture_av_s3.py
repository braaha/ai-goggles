#!/usr/bin/env python3


import argparse
import subprocess
import time
from datetime import datetime
from pathlib import Path

import boto3
from botocore.exceptions import BotoCoreError, NoCredentialsError, ClientError
from picamera2 import Picamera2, encoders


def record_video(video_path: Path, seconds: int, width: int, height: int, bitrate: int) -> None:
    """Record H264 video from the Pi camera to `video_path`."""
    picam2 = Picamera2()
    config = picam2.create_video_configuration(main={"size": (width, height)})
    picam2.configure(config)

    encoder = encoders.H264Encoder(bitrate=bitrate)

    picam2.start_recording(encoder, str(video_path))
    try:
        time.sleep(seconds)
    finally:
        picam2.stop_recording()
        picam2.close()


def record_audio_arecord(audio_path: Path, seconds: int, samplerate: int, channels: int) -> None:
    """
    Record audio using ALSA `arecord` from the Google Voice HAT.

    Uses card 1, device 0: plughw:1,0 which we already tested with:
      arecord -D plughw:1,0 -f cd -d 5 test.wav
    """
    # Map channels + samplerate to arecord args
    # -f cd means 16 bit, 44100 Hz, stereo
    # So we force samplerate=44100, channels=2 for now to match that.
    cmd = [
        "arecord",
        "-D",
        "plughw:1,0",
        "-f",
        "cd",
        "-d",
        str(seconds),
        str(audio_path),
    ]
    print("Running audio cmd:", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("arecord failed:")
        print(result.stderr)
        raise RuntimeError("arecord failed")


def make_mp4_ffmpeg(video_path: Path, audio_path: Path, output_path: Path) -> None:
    """
    Use ffmpeg to merge H264 video + WAV audio into MP4.

    We re-encode the video stream (libx264) instead of copy, so we
    get proper timestamps and the audio actually plays in players.
    """
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-i",
        str(audio_path),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-c:a",
        "aac",
        "-shortest",
        str(output_path),
    ]

    print("Running ffmpeg merge:", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("ffmpeg failed:")
        print(result.stderr)
        raise RuntimeError("ffmpeg failed")

    print("MP4 created:", output_path.resolve())


def upload_to_s3(file_path: Path, bucket: str, key: str) -> None:
    """
    Upload `file_path` to S3 bucket with the given object key.
    Uses default AWS credentials (aws configure).
    """
    s3 = boto3.client("s3")

    print(f"Uploading to S3 bucket='{bucket}', key='{key}'")
    try:
        s3.upload_file(str(file_path), bucket, key)
    except (BotoCoreError, NoCredentialsError, ClientError) as e:
        print("S3 upload failed:", e)
        raise
    print("Upload complete.")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Record Pi video + mic audio, make MP4, upload to S3."
    )
    ap.add_argument("--seconds", type=int, default=10, help="Recording duration in seconds.")
    ap.add_argument("--width", type=int, default=1280, help="Video width.")
    ap.add_argument("--height", type=int, default=720, help="Video height.")
    ap.add_argument("--bitrate", type=int, default=10_000_000, help="Video bitrate in bps.")
    ap.add_argument(
        "--bucket",
        type=str,
        required=True,
        help="Target S3 bucket name.",
    )
    ap.add_argument(
        "--prefix",
        type=str,
        default="ai-goggles/",
        help="S3 key prefix (folder-like path, can be empty).",
    )
    ap.add_argument(
        "--device-id",
        type=str,
        default="pi-goggles-1",
        help="Logical device id to include in S3 key path.",
    )
    return ap.parse_args()


def main() -> None:
    args = parse_args()

    # Timestamp for filenames
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Local paths
    video_path = Path(f"video_{ts}.h264")
    audio_path = Path(f"audio_{ts}.wav")
    final_path = Path(f"final_{ts}.mp4")

    print("Starting recording for", args.seconds, "seconds")

    # 1) Start audio recording (blocking here for now, but we can overlap later if needed)
    record_audio_arecord(audio_path, args.seconds, samplerate=44100, channels=2)

    # 2) Record video
    record_video(video_path, args.seconds, args.width, args.height, args.bitrate)

    print(f"Saved raw video: {video_path.resolve()}")
    print(f"Saved raw audio: {audio_path.resolve()}")

    # 3) Merge into MP4
    make_mp4_ffmpeg(video_path, audio_path, final_path)


    prefix = args.prefix
    if prefix and not prefix.endswith("/"):
        prefix += "/"

    s3_key = f"{prefix}{args.device_id}/{final_path.name}"

    # 5) Upload to S3
    upload_to_s3(final_path, args.bucket, s3_key)

    print("DONE")
    print("Video file:", video_path.name)
    print("Audio file:", audio_path.name)
    print("Final MP4:", final_path.name)
    print("S3 object key:", s3_key)


if __name__ == "__main__":
    main()
