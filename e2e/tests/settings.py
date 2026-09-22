"""Runtime configuration for the pipeline e2e tests, read from environment."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    db_dsn: str
    redis_url: str
    s3_endpoint: str
    s3_access_key: str
    s3_secret_key: str
    s3_bucket: str
    conversion_stream: str
    conversion_group: str
    dedupe_stream: str
    dedupe_group: str
    compression_stream: str
    pagecount_stream: str
    ocr_stream: str
    ocr_group: str
    activemq_url: str
    activemq_user: str
    activemq_password: str
    activemq_queue: str
    stage_timeout: float
    samples_dir: str
    bcgovcode: str = "CITZ"


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required; run through ./e2e/run.sh")
    return value


def load() -> Settings:
    return Settings(
        db_dsn=_require("E2E_DB_DSN"),
        redis_url=_require("E2E_REDIS_URL"),
        s3_endpoint=_require("E2E_S3_ENDPOINT"),
        s3_access_key=_require("E2E_S3_ACCESS_KEY"),
        s3_secret_key=_require("E2E_S3_SECRET_KEY"),
        s3_bucket=_require("E2E_S3_BUCKET"),
        conversion_stream=_require("E2E_CONVERSION_STREAM"),
        conversion_group=_require("E2E_CONVERSION_GROUP"),
        dedupe_stream=_require("E2E_DEDUPE_STREAM"),
        dedupe_group=_require("E2E_DEDUPE_GROUP"),
        compression_stream=_require("E2E_COMPRESSION_STREAM"),
        pagecount_stream=_require("E2E_PAGECOUNT_STREAM"),
        ocr_stream=_require("E2E_OCR_STREAM"),
        ocr_group=_require("E2E_OCR_GROUP"),
        activemq_url=_require("E2E_ACTIVEMQ_URL"),
        activemq_user=_require("E2E_ACTIVEMQ_USER"),
        activemq_password=_require("E2E_ACTIVEMQ_PASSWORD"),
        activemq_queue=_require("E2E_ACTIVEMQ_QUEUE"),
        stage_timeout=float(os.environ.get("E2E_STAGE_TIMEOUT", "120")),
        samples_dir=os.environ.get("E2E_SAMPLES_DIR", "/samples"),
    )
