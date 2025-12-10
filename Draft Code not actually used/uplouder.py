#for attempting to use amazon aws

import boto3
import os
from pathlib import Path
import shutil

BUCKET = "ai-goggles-recordings"
MEDIA_DIR = Path("/home/aigoggles/ai-goggles/media")
UPLOADED_DIR = MEDIA_DIR / "uploaded"

def upload_file(path: Path):
    s3 = boto3.client("s3")
    key = f"videos/{path.name}"
    s3.upload_file(str(path), BUCKET, key)
    print(f"Uploaded {path.name} → s3://{BUCKET}/{key}")

def main():
    UPLOADED_DIR.mkdir(exist_ok=True)

    for file in MEDIA_DIR.glob("session_*.mp4"):
        upload_file(file)
        shutil.move(file, UPLOADED_DIR / file.name)

if __name__ == "__main__":
    main()
