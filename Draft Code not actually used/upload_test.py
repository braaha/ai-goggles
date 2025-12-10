#for attempting to use amazon aws

import boto3
s3 = boto3.client("s3")

s3.upload_file("test.mp4", "ai-goggles-recordings", "test/test.mp4")
