#!/usr/bin/env python3
import argparse
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs import FileOutput


def record_audio(audio_path: Path, seconds: int, device: str = "plughw:1,0"):
    """
    Record audio using arecord for the specified number of seconds.
    """
    cmd = [
        "arecord",
        "-D", device,
        "-f", "S16_LE",
        "-r", "44100",
        "-c", "2",
        "-d", str(seconds),
        str(audio_path),
    ]
    print(f"[AUDIO] Running audio command: {' '.join(cmd)}")
    sys.stdout.flush()
    # Use Popen so audio can run while video records
    return subprocess.Popen(cmd)


def record_video(video_path: Path, seconds: int, width: int = 1280, height: int = 720, fps: int = 30):
    """
    Record video using Picamera2 (libcamera) to an .h264 file.
    """
    print(f"[VIDEO] Starting recording to {video_path.name} ({width}x{height}, {fps} fps)")
    sys.stdout.flush()

    picam2 = Picamera2()
    video_config = picam2.create_video_configuration(
        main={"size": (width, height)}
    )
    picam2.configure(video_config)

    encoder = H264Encoder()
    output = FileOutput(str(video_path))

    picam2.start_recording(encoder, output)
    time.sleep(seconds)
    picam2.stop_recording()

    print("[VIDEO] Stopping recording")
    sys.stdout.flush()


def merge_av_to_mp4(video_path: Path, audio_path: Path, final_path: Path, fps: int = 30):
    """
    Use ffmpeg to merge the .h264 video and .wav audio into an .mp4 file.
    This follows the same pattern that already worked for you.
    """
    cmd = [
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
    print(f"[FFMPEG] Running: {' '.join(cmd)}")
    sys.stdout.flush()

    subprocess.run(cmd, check=True)
    print(f"[FFMPEG] MP4 created: {final_path}")
    sys.stdout.flush()


def upload_to_s3(file_path: Path, bucket: str, key: str, region: str):
    """
    Upload the given file to S3.
    """
    print(f"[S3] Uploading to bucket='{bucket}', key='{key}', region='{region}'")
    sys.stdout.flush()

    s3 = boto3.client("s3", region_name=region)

    try:
        s3.upload_file(str(file_path), bucket, key)
    except (BotoCoreError, ClientError) as e:
        print("[S3] Upload failed with error:")
        print(e)
        raise

    print("[S3] Upload successful.")
    sys.stdout.flush()


def parse_args():
    parser = argparse.ArgumentParser(
        description="Record audio+video (arecord + Picamera2), merge with ffmpeg, and upload MP4 to S3."
    )
    parser.add_argument(
        "--seconds",
        type=int,
        default=5,
        help="Recording duration in seconds (default: 5)",
    )
    parser.add_argument(
        "--bucket",
        required=True,
        help="S3 bucket name (you have: ai-goggles-recordings)",
    )
    parser.add_argument(
        "--prefix",
        default="ai-goggles",
        help="S3 key prefix (default: ai-goggles)",
    )
    parser.add_argument(
        "--device-id",
        default="pi-goggles-1",
        help="Logical device id to include in the key path",
    )
    parser.add_argument(
        "--region",
        default="us-east-2",
        help="AWS region for S3 client (default: us-east-2)",
    )
    parser.add_argument(
        "--audio-device",
        default="plughw:1,0",
        help="ALSA device for arecord (default: plughw:1,0)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    seconds = args.seconds

    # Timestamp for filenames
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    video_path = Path(f"video_{ts}.h264")
    audio_path = Path(f"audio_{ts}.wav")
    final_path = Path(f"final_{ts}.mp4")

    print("==========================================")
    print(" Starting capture")
    print(f"  Seconds:     {seconds}")
    print(f"  Resolution:  1280x720")
    print(f"  FPS:         30")
    print(f"  Audio rate:  44100 Hz")
    print(f"  Audio ch:    2")
    print(f"  Device:      {args.audio_device}")
    print("==========================================")
    sys.stdout.flush()

    try:
        # Start audio first (like your working flow), then video
        audio_proc = record_audio(audio_path, seconds, device=args.audio_device)
        record_video(video_path, seconds, width=1280, height=720, fps=30)

        # Wait for audio to finish
        audio_ret = audio_proc.wait()
        if audio_ret != 0:
            raise RuntimeError(f"arecord failed with exit code {audio_ret}")

        print(f"[AUDIO] Audio recorded to: {audio_path}")
        print(f"[INFO] Saved video: {video_path.resolve()}")
        print(f"[INFO] Saved audio: {audio_path.resolve()}")
        sys.stdout.flush()

        # Merge into MP4
        merge_av_to_mp4(video_path, audio_path, final_path, fps=30)

        print("==========================================")
        print(" DONE")
        print(f" Video file: {video_path.name}")
        print(f" Audio file: {audio_path.name}")
        print(f" Final MP4:  {final_path.name}")
        print("==========================================")
        sys.stdout.flush()

    except Exception as e:
        print("Error during recording or merging:")
        print(e)
        sys.stdout.flush()
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
