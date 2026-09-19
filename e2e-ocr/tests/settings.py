"""Runtime configuration for the OCR e2e tests, read from environment."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    db_dsn: str
    s3_endpoint: str
    s3_access_key: str
    s3_secret_key: str
    s3_bucket: str
    activemq_url: str
    activemq_user: str
    activemq_password: str
    activemq_queue: str
    mock_azure_url: str
    status_api_url: str
    stage_timeout: float
    max_concurrent: int
    samples_dir: str
    worker_log_dir: str


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required; run through ./e2e-ocr/run.sh")
    return value


def load() -> Settings:
    return Settings(
        db_dsn=_require("E2E_OCR_DB_DSN"),
        s3_endpoint=_require("E2E_OCR_S3_ENDPOINT"),
        s3_access_key=_require("E2E_OCR_S3_ACCESS_KEY"),
        s3_secret_key=_require("E2E_OCR_S3_SECRET_KEY"),
        s3_bucket=_require("E2E_OCR_S3_BUCKET"),
        activemq_url=_require("E2E_OCR_ACTIVEMQ_URL"),
        activemq_user=_require("E2E_OCR_ACTIVEMQ_USER"),
        activemq_password=_require("E2E_OCR_ACTIVEMQ_PASSWORD"),
        activemq_queue=_require("E2E_OCR_ACTIVEMQ_QUEUE"),
        mock_azure_url=_require("E2E_OCR_MOCK_AZURE_URL"),
        status_api_url=_require("E2E_OCR_STATUS_API_URL"),
        stage_timeout=float(os.environ.get("E2E_OCR_STAGE_TIMEOUT", "120")),
        max_concurrent=int(os.environ.get("E2E_OCR_MAX_CONCURRENT", "1")),
        samples_dir=os.environ.get("E2E_OCR_SAMPLES_DIR", "/samples"),
        worker_log_dir=os.environ.get("E2E_OCR_WORKER_LOG_DIR", "/var/log/ocr"),
    )
