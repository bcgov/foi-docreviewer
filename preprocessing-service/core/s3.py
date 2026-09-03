"""S3 access for the worker: fetch the source PDF, upload the restored one.

Credentials and region come from the standard boto3 resolution chain (env vars,
~/.aws, container/instance role) - nothing S3-auth-related lives in settings.
The endpoint is a setting (S3_ENDPOINT_URL): unset means real AWS S3, set means
an S3-compatible store such as BC Gov OCIO object storage. boto3 is synchronous,
so every call is run in a worker thread to keep the event loop (consumer +
health server) free.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from urllib.parse import urlparse

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from config.logging import get_logger
from config.settings import get_settings

logger = get_logger(__name__)


class S3Error(Exception):
    """Raised when an S3 object cannot be fetched or stored."""


_client = None


def get_s3_client():
    """
    Process-wide S3 client.
    """
    global _client
    if _client is None:
        s = get_settings()
        cfg = {
            "connect_timeout": s.S3_CONNECT_TIMEOUT_SECONDS,
            "read_timeout": s.S3_READ_TIMEOUT_SECONDS,
            "retries": {"max_attempts": s.S3_MAX_ATTEMPTS, "mode": "standard"},
        }
        if s.S3_FORCE_PATH_STYLE:
            cfg["s3"] = {"addressing_style": "path"}
        _client = boto3.client(
            "s3",
            endpoint_url=s.S3_ENDPOINT_URL or None,
            config=Config(**cfg),
        )
    return _client


def close_s3_client() -> None:
    """Dispose of the process-wide S3 client. Called on worker shutdown."""
    global _client
    if _client is not None:
        _client.close()
        _client = None
        logger.debug("S3 client closed")


def parse_s3_uri(uri: str) -> tuple[str, str]:
    """'s3://bucket/path/to/key' -> ('bucket', 'path/to/key')."""
    parsed = urlparse(uri)
    if parsed.scheme != "s3" or not parsed.netloc or not parsed.path.lstrip("/"):
        raise S3Error(f"not a valid s3:// URI: {uri!r}")
    return parsed.netloc, parsed.path.lstrip("/")


def suffix_uri(uri: str, suffix: str) -> str:
    """Append `suffix` to the filename stem, keeping bucket/prefix/extension.

    's3://bucket/dir/name.pdf', 'PREPROCESSED' -> 's3://b/dir/namePREPROCESSED.pdf'
    """
    head, sep, tail = uri.rpartition("/")
    stem, dot, ext = tail.rpartition(".")
    tail = f"{stem}{suffix}.{ext}" if dot else f"{tail}{suffix}"
    return f"{head}{sep}{tail}"


async def fetch_pdf(source_uri: str, dst: str | Path) -> Path:
    """Download the object at `source_uri` to `dst`. Raises S3Error on failure."""
    bucket, key = parse_s3_uri(source_uri)
    dst = Path(dst)
    await asyncio.to_thread(_fetch_sync, bucket, key, dst)
    logger.info("PDF fetched from S3", uri=source_uri, path=str(dst))
    return dst


async def upload_pdf(src: str | Path, dest_uri: str) -> str:
    """Upload the local file `src` to `dest_uri`. Returns `dest_uri`."""
    bucket, key = parse_s3_uri(dest_uri)
    await asyncio.to_thread(_upload_sync, Path(src), bucket, key)
    logger.info("PDF uploaded to S3", uri=dest_uri)
    return dest_uri


def _fetch_sync(bucket: str, key: str, dst: Path) -> None:
    client = get_s3_client()
    max_bytes = get_settings().MAX_PDF_BYTES

    try:
        head = client.head_object(Bucket=bucket, Key=key)
    except (ClientError, BotoCoreError) as e:
        raise S3Error(f"head s3://{bucket}/{key}: {e}") from e

    size = head.get("ContentLength", 0)
    if size > max_bytes:
        raise S3Error(f"object is {size} bytes, over the {max_bytes} cap")

    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        client.download_file(bucket, key, str(dst))
    except (ClientError, BotoCoreError) as e:
        raise S3Error(f"get s3://{bucket}/{key}: {e}") from e

    with dst.open("rb") as fh:
        if fh.read(5) != b"%PDF-":
            raise S3Error(f"s3://{bucket}/{key} is not a PDF (missing %PDF- header)")


def _upload_sync(src: Path, bucket: str, key: str) -> None:
    client = get_s3_client()
    try:
        client.upload_file(
            str(src), bucket, key, ExtraArgs={"ContentType": "application/pdf"}
        )
    except (ClientError, BotoCoreError) as e:
        raise S3Error(f"put s3://{bucket}/{key}: {e}") from e
