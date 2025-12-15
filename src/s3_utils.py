"""Minimal S3 helpers. Only used when ENABLE_S3=true."""
import os
import boto3

def s3_client():
    return boto3.client(
        "s3",
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=os.getenv("AWS_REGION")
    )

def upload_bytes_to_s3(bucket: str, key: str, data: bytes):
    client = s3_client()
    client.put_object(Bucket=bucket, Key=key, Body=data)
    return True

def generate_presigned_get(bucket: str, key: str, expires_in: int = 21600):
    client = s3_client()
    return client.generate_presigned_url("get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=expires_in)