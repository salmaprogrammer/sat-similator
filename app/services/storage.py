"""Storage abstraction: local filesystem in dev, S3-compatible in prod."""
from __future__ import annotations
import os
import uuid
from pathlib import Path
from typing import BinaryIO

from flask import current_app


def save_upload(file_stream: BinaryIO, filename: str) -> str:
    """Save an uploaded file and return a URL/path handle.

    Returns a `file://` path in dev (local filesystem) or `s3://bucket/key` in prod.
    """
    if current_app.config.get("S3_BUCKET"):
        return _save_s3(file_stream, filename)
    return _save_local(file_stream, filename)


def read_file(url: str) -> bytes:
    """Read back a file previously stored via save_upload."""
    if url.startswith("s3://"):
        return _read_s3(url)
    if url.startswith("file://"):
        path = url[len("file://"):]
    else:
        path = url
    with open(path, "rb") as f:
        return f.read()


def _save_local(stream: BinaryIO, filename: str) -> str:
    folder = Path(current_app.config["UPLOAD_FOLDER"])
    folder.mkdir(parents=True, exist_ok=True)
    ext = Path(filename).suffix or ""
    dest = folder / f"{uuid.uuid4().hex}{ext}"
    with open(dest, "wb") as f:
        f.write(stream.read())
    return f"file://{dest}"


def _save_s3(stream: BinaryIO, filename: str) -> str:
    import boto3
    cfg = current_app.config
    client = boto3.client(
        "s3",
        aws_access_key_id=cfg["S3_ACCESS_KEY_ID"],
        aws_secret_access_key=cfg["S3_SECRET_ACCESS_KEY"],
        endpoint_url=cfg["S3_ENDPOINT_URL"] or None,
        region_name=cfg["S3_REGION"],
    )
    ext = os.path.splitext(filename)[1] or ""
    key = f"imports/{uuid.uuid4().hex}{ext}"
    client.put_object(Bucket=cfg["S3_BUCKET"], Key=key, Body=stream.read())
    return f"s3://{cfg['S3_BUCKET']}/{key}"


def _read_s3(url: str) -> bytes:
    import boto3
    _, _, rest = url.partition("s3://")
    bucket, _, key = rest.partition("/")
    cfg = current_app.config
    client = boto3.client(
        "s3",
        aws_access_key_id=cfg["S3_ACCESS_KEY_ID"],
        aws_secret_access_key=cfg["S3_SECRET_ACCESS_KEY"],
        endpoint_url=cfg["S3_ENDPOINT_URL"] or None,
        region_name=cfg["S3_REGION"],
    )
    return client.get_object(Bucket=bucket, Key=key)["Body"].read()
