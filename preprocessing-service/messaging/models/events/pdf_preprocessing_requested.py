from urllib.parse import urlparse
from pydantic import BaseModel, Field, field_validator


class PdfPreprocessingRequestedEvent(BaseModel):
    """
    Payload for PdfPreprocessingRequested -- the *input* to the processing step.

    `source_uri` is an `s3://bucket/key` URI or a supported HTTPS object-store
    URL the worker can normalize and read with its configured credentials.
    `job_id` is the caller's idempotency key:
    republishing the same job_id is a logged no-op, not duplicate work.
    """

    job_id: str = Field(min_length=1, max_length=64)
    source_uri: str = Field(min_length=1, max_length=2048)
    legacy_payload: dict[str, object] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}

    @field_validator("source_uri")
    @classmethod
    def _must_be_object_store_uri(cls, v: str) -> str:
        parsed = urlparse(v)
        if parsed.scheme == "s3" and parsed.netloc and parsed.path.lstrip("/"):
            return v
        if parsed.scheme == "https" and parsed.netloc and parsed.path.count("/") >= 2:
            return v
        raise ValueError("source_uri must be an s3://bucket/key or HTTPS object-store URI")
