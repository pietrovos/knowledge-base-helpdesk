"""S3-compatible object storage (MinIO locally, S3 in production). The bucket is private;
browsers only ever receive short-lived presigned GET URLs."""

import contextlib
import time
from functools import lru_cache

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError, EndpointConnectionError

from app.config import get_settings


def _client(endpoint: str | None):
    s = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name=s.s3_region,
        aws_access_key_id=s.s3_access_key,
        aws_secret_access_key=s.s3_secret_key,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


@lru_cache
def s3():
    return _client(get_settings().s3_endpoint_url)


@lru_cache
def s3_public():
    s = get_settings()
    return _client(s.s3_public_endpoint_url or s.s3_endpoint_url)


def ensure_bucket(attempts: int = 30) -> None:
    bucket = get_settings().s3_bucket
    for i in range(attempts):
        try:
            s3().head_bucket(Bucket=bucket)
            break
        except ClientError:
            s3().create_bucket(Bucket=bucket)
            break
        except EndpointConnectionError:
            if i == attempts - 1:
                raise
            time.sleep(1)
    # MinIO does not implement public access blocks; its buckets are private by default.
    with contextlib.suppress(ClientError):
        s3().put_public_access_block(
            Bucket=bucket,
            PublicAccessBlockConfiguration={
                "BlockPublicAcls": True,
                "IgnorePublicAcls": True,
                "BlockPublicPolicy": True,
                "RestrictPublicBuckets": True,
            },
        )


def put_object(key: str, data: bytes, content_type: str) -> None:
    s3().put_object(Bucket=get_settings().s3_bucket, Key=key, Body=data, ContentType=content_type)


def get_object(key: str) -> bytes:
    return s3().get_object(Bucket=get_settings().s3_bucket, Key=key)["Body"].read()


def presigned_get(key: str, filename: str, expires: int = 300) -> str:
    return s3_public().generate_presigned_url(
        "get_object",
        Params={
            "Bucket": get_settings().s3_bucket,
            "Key": key,
            "ResponseContentDisposition": f'attachment; filename="{filename}"',
        },
        ExpiresIn=expires,
    )
