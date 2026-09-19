"""Thin clients over Postgres, S3, ActiveMQ, the mock Azure and the status API."""
from __future__ import annotations

import json
import time
from typing import Callable, TypeVar

import boto3
import psycopg
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
            self.put_bytes(key, handle.read(), content_type)

    def put_bytes(self, key: str, data: bytes, content_type: str = "application/pdf") -> None:
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data, ContentType=content_type)

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
        """The path-style URL the worker receives in `s3filepath` and derives the OCR key from."""
        return f"{self._endpoint}/{self._bucket}/{key}"


class ActiveMQ:
    def __init__(self, settings: Settings) -> None:
        self._url = settings.activemq_url
        self._auth = (settings.activemq_user, settings.activemq_password)
        self._queue = settings.activemq_queue

    def reachable(self) -> bool:
        # Probe a scratch queue so we never steal a message from the worker's queue.
        response = requests.get(
            f"{self._url}/e2e-ocr-probe",
            params={"type": "queue", "oneShot": "true", "readTimeout": "200"},
            auth=self._auth,
            timeout=5,
        )
        return response.status_code in (200, 204)

    def publish(self, payload: dict) -> None:
        """POST the way OCRServices' activemq.Client.Push does."""
        response = requests.post(
            f"{self._url}?destination=queue://{self._queue}",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
            auth=self._auth,
            timeout=10,
        )
        response.raise_for_status()


class MockAzure:
    def __init__(self, settings: Settings) -> None:
        self._url = settings.mock_azure_url

    def healthy(self) -> bool:
        try:
            return requests.get(f"{self._url}/healthz", timeout=3).status_code == 200
        except requests.RequestException:
            return False

    def reset(self) -> None:
        requests.delete(f"{self._url}/_control", timeout=5).raise_for_status()

    def scenario(self, **scenario) -> dict:
        response = requests.post(f"{self._url}/_control", json=scenario, timeout=5)
        response.raise_for_status()
        return response.json()

    def stats(self) -> dict:
        response = requests.get(f"{self._url}/_stats", timeout=5)
        response.raise_for_status()
        return response.json()


class StatusApi:
    def __init__(self, settings: Settings) -> None:
        self._url = settings.status_api_url

    def reachable(self) -> bool:
        try:
            # No secret header → 403 from customHeaderMiddleware proves the router is up.
            return requests.post(f"{self._url}/api/documentocrjob", timeout=3).status_code == 403
        except requests.RequestException:
            return False
