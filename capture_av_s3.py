#!/usr/bin/env python3
import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import boto3
from botocore.exceptions import BotoCoreError, ClientError


def run_cmd(cmd_list, label=None, check=True):
    """Run a shell command and stream output."""
    if label:
        print(label)
    print(" ", " ".join(cmd_list))
    sys.stdout.flush()

    result = subprocess.run(cmd_list)
    if check and result.returncode != 0:
        raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(cmd_list)}")
    return result


def record_av(seconds, width, height, fps, audio_device):
    """
    Record audio and video for the given duration.

    Returns paths: (video_path, audio_path, final_mp4_path, timestamp_str)
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    cwd = Path.cwd()

    video_name = f"video_{ts}.h264"
    audio_name = f"audio_{ts}.wav"
    final_name = f"final_{ts}.mp4"

    video_path = cwd / video_name
    audio_path = cwd / audio_name
    final_path = cwd / final_name

    # 1) Start libcamera-vid for a fixed duration (milliseconds)
    ms = int(seconds * 1000)
    video_cmd = [
        "libcamera-vid",
        "-t", str(ms),
        "-n",
        "--width", str(width),
        "--height", str(height),
        "--framerate", str(fps),
        "--codec", "h264",
        "-o", str(video_path),
    ]

    # 2) Start arecord for fixed duration
    audio_cmd = [
        "arecord",
        "-D", audio_device,
        "-f", "S16_LE",
        "-r", "44100",
        "-c", "2",
        "-d", str(seconds),
        str(audio_path),
    ]

    print("==========================================")
    print(" Starting capture")
    print(f"  Seconds:     {seconds}")
    print(f"  Resolution:  {width}x{height}")
    print(f"  FPS:         {fps}")
    print(f"  Audio rate:  44100 Hz")
    print(f"  Audio ch:    2")
    print(f"  Device:      {audio_device}")
    print("==========================================")
    sys.stdout.flush()

    # Start video first, then audio right after so they overlap
    print("[VIDEO] Starting libcamera-vid...")
    video_proc = subprocess.Popen(video_cmd)

    print("[AUDIO] Starting arecord...")
    audio_proc = subprocess.Popen(audio_cmd)

    # Wait for both to finish
    video_proc.wait()
    audio_proc.wait()

    if video_proc.returncode != 0:
        raise RuntimeError(f"libcamera-vid failed with code {video_proc.returncode}")
    if audio_proc.returncode != 0:
        raise RuntimeError(f"arecord failed with code {audio_proc.returncode}")

    print(f"[INFO] Saved video: {video_path}")
    print(f"[INFO] Saved audio: {audio_path}")
    sys.stdout.flush()

    # 3) Merge with ffmpeg using libx264 + aac (the combo that gave you working sound)
    ffmpeg_cmd = [
        "ffmpeg",
        "-y",
        "-r", str(fps),
        "-i", str(video_path),
        "-i", str(audio_path),
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",
        "-c:a", "aac",
        "-shortest",
        str(final_path),
    ]

    print("[FFMPEG] Running merge:")
    print(" ", " ".join(ffmpeg_cmd))
    sys.stdout.flush()

    run_cmd(ffmpeg_cmd, check=True)

    print(f"[FFMPEG] MP4 created: {final_path}")
    print("==========================================")
    print(" DONE")
    print(f" Video file: {video_path.name}")
    print(f" Audio file: {audio_path.name}")
    print(f" Final MP4:  {final_path.name}")
    print("==========================================")
    sys.stdout.flush()

    return video_path, audio_path, final_path, ts


def upload_to_s3(file_path: Path, bucket: str, key: str, region: str):
    """Upload the given file to S3."""
    print(f"Uploading to S3 bucket='{bucket}', key='{key}', region='{region}'")
    sys.stdout.flush()

    # Use explicit region to match your bucket (us-east-2)
    s3 = boto3.client("s3", region_name=region)

    try:
        s3.upload_file(str(file_path), bucket, key)
    except (BotoCoreError, ClientError) as e:
        print("S3 upload failed with error:")
        print(e)
        raise

    print("Upload successful.")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Record audio+video on Pi and upload merged MP4 to S3."
    )

    parser.add_argument("--seconds", type=int, default=5,
                        help="Recording duration in seconds (default: 5)")
    parser.add_argument("--width", type=int, default=1280,
                        help="Video width (default: 1280)")
    parser.add_argument("--height", type=int, default=720,
                        help="Video height (default: 720)")
    parser.add_argument("--fps", type=int, default=30,
                        help="Video frames per second (default: 30)")

    parser.add_argument("--audio-device", type=str, default="plughw:1,0",
                        help="arecord device (default: plughw:1,0)")

    parser.add_argument("--bucket", required=True,
                        help="S3 bucket name (you have: ai-goggles-recordings)")
    parser.add_argument("--prefix", default="ai-goggles",
                        help="S3 key prefix (default: ai-goggles)")
    parser.add_argument("--device-id", default="pi-goggles-1",
                        help="Logical device id to include in the key path")

    parser.add_argument("--region", default="us-east-2",
                        help="AWS region for S3 client (default: us-east-2)")

    return parser.parse_args()


def main():
    args = parse_args()

    try:
        video_path, audio_path, final_path, ts = record_av(
            seconds=args.seconds,
            width=args.width,
            height=args.height,
            fps=args.fps,
            audio_device=args.audio_device,
        )
    except Exception as e:
        print("Error during recording or merging:")
        print(e)
        sys.exit(1)

    # Build S3 key: prefix/device-id/filename
    s3_key = f"{args.prefix.rstrip('/')}/{args.device_id}/{final_path.name}"

    try:
        upload_to_s3(final_path, args.bucket, s3_key, args.region)
    except Exception as e:
        print("S3 upload failed:")
        print(e)
        sys.exit(2)


if __name__ == "__main__":
    main()
