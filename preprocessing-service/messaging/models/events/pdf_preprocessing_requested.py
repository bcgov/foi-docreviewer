from pydantic import BaseModel, Field, field_validator


class PdfPreprocessingRequestedEvent(BaseModel):
    """
    Payload for PdfPreprocessingRequested -- the *input* to the processing step.

    `source_uri` is a full `s3://bucket/key` URI the worker can read with its
    configured credentials. `job_id` is the caller's idempotency key:
    republishing the same job_id is a logged no-op, not duplicate work.
    """

    job_id: str = Field(min_length=1, max_length=64)
    source_uri: str = Field(min_length=1, max_length=2048)

    model_config = {"extra": "forbid"}

    @field_validator("source_uri")
    @classmethod
    def _must_be_s3_uri(cls, v: str) -> str:
        if not v.startswith("s3://") or "/" not in v[len("s3://") :]:
            raise ValueError("source_uri must be an s3://bucket/key URI")
        return v
