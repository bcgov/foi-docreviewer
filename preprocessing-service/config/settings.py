# config/settings.py
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # -------------------------
    # Environment Metadata
    # -------------------------
    ENVIRONMENT: str = "development"  # development | staging | production
    SERVICE_NAME: str = "pdf-preprocessing"
    SERVICE_VERSION: str = "0.1.0"

    # SERVICE_NAME / SERVICE_VERSION / ENVIRONMENT have exactly one consumer
    # now: the OpenTelemetry Resource in config/tracing.py, which stamps them
    # on every exported span. The /info endpoint that used to serve them is
    # gone — the collector has the same three values.

    # -------------------------
    # Health probe server
    # -------------------------
    HEALTH_PORT: int = 8000

    # -------------------------
    # Handler state store
    # -------------------------
    STATE_TTL_SECONDS: int = 3600

    # -------------------------
    # Redis Streams Messaging
    # -------------------------
    REDIS_STREAM_URL: str = "redis://localhost:6379/1"
    STREAM_NAME: str = "pdf.preprocessing.requests"
    CONSUMER_GROUP: str = "pdf_preprocessing_v1"
    OUTPUT_STREAM_NAME: str = "pdf.preprocessing.completed"
    STREAM_POLL_INTERVAL_MS: int = 1000  # XREADGROUP BLOCK duration

    # -------------------------
    # Consumer reliability
    # -------------------------
    CONSUMER_BATCH_SIZE: int = 10
    CONSUMER_MAX_RETRIES: int = 3
    CONSUMER_RETRY_BACKOFF_MS: int = 500
    CONSUMER_CLAIM_MIN_IDLE_MS: int = 60_000
    DLQ_STREAM_NAME: str = ""  # empty -> derived from STREAM_NAME

    # -------------------------
    # PDF processing
    # -------------------------
    # Local scratch for the downloaded source and the restored output before
    # upload; both files are deleted per job.
    WORK_DIR: str = "/tmp/pdf-preprocessing"
    MAX_PDF_BYTES: int = 100 * 1024 * 1024  # 100 MiB; source objects over this fail
    OUTPUT_FILENAME_SUFFIX: str = "PREPROCESSED"

    # Credentials and region come from the standard boto3 chain (env, ~/.aws,
    # instance role) -- not from settings.
    #
    # S3_ENDPOINT_URL: leave unset for real AWS S3. Set it for an
    # S3-compatible store, e.g. BC Gov OCIO object storage:
    #   S3_ENDPOINT_URL=https://citz-foi-prod.objectstore.gov.bc.ca
    #   S3_FORCE_PATH_STYLE=true   (bucket in the path, not the host)
    S3_ENDPOINT_URL: Optional[str] = None
    S3_FORCE_PATH_STYLE: bool = False
    S3_CONNECT_TIMEOUT_SECONDS: float = 10.0
    S3_READ_TIMEOUT_SECONDS: float = 60.0
    S3_MAX_ATTEMPTS: int = 3

    # -------------------------
    # Logging
    # -------------------------
    LOG_LEVEL: str = "INFO"
    JSON_LOGS: bool = False

    # -------------------------
    # OpenTelemetry / Tracing
    # -------------------------
    OTEL_EXPORTER_OTLP_ENDPOINT: Optional[str] = None
    OTEL_EXPORTER_OTLP_ENDPOINT_ENABLE_FALLBACK: bool = False

    # -------------------------
    # Pydantic Config
    # -------------------------
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def dlq_stream(self) -> str:
        """Dead-letter stream; defaults to '<STREAM_NAME>:dlq'."""
        return self.DLQ_STREAM_NAME or f"{self.STREAM_NAME}:dlq"


@lru_cache
def get_settings() -> Settings:
    return Settings()
