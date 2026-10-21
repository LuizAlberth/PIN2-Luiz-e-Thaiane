import hashlib
import os
from pathlib import Path
import boto3
from botocore.config import Config

BUCKET = os.getenv('S3_BUCKET', 'pin2-scenes')
ENDPOINT = os.getenv('S3_ENDPOINT', '')
LOCAL_DIR = Path(os.getenv('LOCAL_STORAGE', './storage'))

def client():
    return boto3.client('s3', endpoint_url=ENDPOINT or None,
        aws_access_key_id=os.getenv('S3_ACCESS_KEY'), aws_secret_access_key=os.getenv('S3_SECRET_KEY'),
        config=Config(signature_version='s3v4'))

def put(key: str, data: bytes) -> str:
    checksum = hashlib.sha256(data).hexdigest()
    if ENDPOINT:
        c = client()
        try:
            c.head_bucket(Bucket=BUCKET)
        except Exception:
            c.create_bucket(Bucket=BUCKET)
        c.put_object(Bucket=BUCKET, Key=key, Body=data, ContentType='image/png')
    else:
        target = LOCAL_DIR / key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return checksum

def get(key: str) -> bytes:
    if ENDPOINT:
        return client().get_object(Bucket=BUCKET, Key=key)['Body'].read()
    return (LOCAL_DIR / key).read_bytes()
