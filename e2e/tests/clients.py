"""Thin clients over Postgres, Redis, S3 and ActiveMQ plus a bounded poller."""
from __future__ import annotations

import json
import time
from typing import Callable, TypeVar

import boto3
import psycopg
import redis as redis_lib
import requests
from botocore.config import Config
from botocore.exceptions import ClientError

from settings import Settings

T = TypeVar("T")


class StageTimeout(AssertionError):
    pass


def wait_until(
    predicate: Callable[[], T | None],
    timeout: float,
    interval: float = 0.5,
    describe: Callable[[], str] | None = None,
) -> T:
    """Poll predicate until it returns a truthy value or timeout elapses."""
    deadline = time.monotonic() + timeout
    while True:
        result = predicate()
        if result:
            return result
        if time.monotonic() >= deadline:
            detail = describe() if describe else "no detail"
            raise StageTimeout(f"timed out after {timeout:.0f}s; last state: {detail}")
        time.sleep(interval)


class Postgres:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    def one(self, sql: str, params: tuple = ()) -> tuple | None:
        with psycopg.connect(self._dsn) as conn:
            return conn.execute(sql, params).fetchone()

    def all(self, sql: str, params: tuple = ()) -> list[tuple]:
        with psycopg.connect(self._dsn) as conn:
            return conn.execute(sql, params).fetchall()

    def execute(self, sql: str, params: tuple = ()) -> None:
        with psycopg.connect(self._dsn) as conn:
            conn.execute(sql, params)
            conn.commit()


class Redis:
    def __init__(self, url: str) -> None:
        self._r = redis_lib.Redis.from_url(url, decode_responses=True)
        # Watermill's redis-stream marshaller (used by CompressionServices/
        # OCRServices to publish `foi:ocr`) stores a msgpack-encoded `metadata`
        # field alongside the JSON `payload`; that field is not valid UTF-8 and
        # crashes a `decode_responses=True` connection on XREVRANGE. Read raw
        # bytes on this second connection and decode only what is UTF-8.
        self._raw = redis_lib.Redis.from_url(url, decode_responses=False)

    def ping(self) -> bool:
        return bool(self._r.ping())

    def xadd(self, stream: str, fields: dict[str, str]) -> str:
        return self._r.xadd(stream, fields)

    def entries(self, stream: str, count: int = 200) -> list[tuple[str, dict[str, str]]]:
        """Newest-first entries; the typed OCR stream keeps its JSON in `payload`."""
        raw_entries = self._raw.xrevrange(stream, count=count)
        decoded: list[tuple[str, dict[str, str]]] = []
        for entry_id, fields in raw_entries:
            decoded_fields: dict[str, str] = {}
            for key, value in fields.items():
                key = key.decode("utf-8")
                if isinstance(value, bytes):
                    try:
                        value = value.decode("utf-8")
                    except UnicodeDecodeError:
                        continue  # binary field (e.g. watermill `metadata`); not needed by callers
                decoded_fields[key] = value
            decoded.append((entry_id.decode("utf-8"), decoded_fields))
        return decoded

    def has_group(self, stream: str, group: str) -> bool:
        try:
            return any(g["name"] == group for g in self._r.xinfo_groups(stream))
        except redis_lib.ResponseError as error:
            if "no such key" in str(error).lower():
                return False
            raise


class S3:
    def __init__(self, settings: Settings) -> None:
        self._bucket = settings.s3_bucket
        self._endpoint = settings.s3_endpoint
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name="us-east-1",
            config=Config(s3={"addressing_style": "path"}, signature_version="s3v4"),
        )

    def ensure_bucket(self) -> None:
        try:
            self._client.create_bucket(Bucket=self._bucket)
        except ClientError as error:
            if error.response["Error"]["Code"] not in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
                raise

    def put(self, key: str, path: str, content_type: str) -> None:
        with open(path, "rb") as handle:
            self._client.put_object(Bucket=self._bucket, Key=key, Body=handle, ContentType=content_type)

    def get(self, key: str) -> bytes:
        return self._client.get_object(Bucket=self._bucket, Key=key)["Body"].read()

    def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except ClientError as error:
            if error.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
                return False
            raise

    def url(self, key: str) -> str:
        """The path-style URL workers receive in `s3filepath`."""
        return f"{self._endpoint}/{self._bucket}/{key}"


class ActiveMQ:
    def __init__(self, settings: Settings) -> None:
        self._url = settings.activemq_url
        self._auth = (settings.activemq_user, settings.activemq_password)
        self._queue = settings.activemq_queue

    def reachable(self) -> bool:
        # ActiveMQ's message REST servlet controls the long-poll wait via
        # `readTimeout`, not `timeout`; the latter is silently ignored and
        # the servlet falls back to its ~20s default, which blew past the
        # client-side timeout below.
        response = requests.get(
            f"{self._url}/{self._queue}",
            params={"type": "queue", "oneShot": "true", "readTimeout": "200"},
            auth=self._auth,
            timeout=5,
        )
        return response.status_code in (200, 204)

    def consume_one(self, timeout_ms: int = 2000) -> dict | None:
        """Consume and return the next JSON message on the queue, or None."""
        response = requests.get(
            f"{self._url}/{self._queue}",
            params={"type": "queue", "oneShot": "true", "readTimeout": str(timeout_ms)},
            auth=self._auth,
            timeout=(timeout_ms / 1000) + 5,
        )
        if response.status_code == 204 or not response.text.strip():
            return None
        response.raise_for_status()
        return json.loads(response.text)
