from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class PdfPreprocessingCompletedEvent(BaseModel):
    """
    Payload for PdfPreprocessingCompleted -- the *output* of the processing
    step, published to OUTPUT_STREAM_NAME for the next service in the pipeline.

    `outcome`:
      - `text_restored`  clip-hidden text was found and restored; `output_uri`
                         is the s3://bucket/key of the repaired PDF
      - `clean`          no hidden text; nothing uploaded, `output_uri` is null

    Counts and `output_uri` are values that did not exist on the inbound event.
    """

    job_id: str = Field(min_length=1, max_length=64)
    outcome: Literal["text_restored", "clean"]
    spans_restored: int = Field(ge=0)
    pages_affected: int = Field(ge=0)
    output_uri: str | None = None
    completed_at: datetime

    model_config = {"extra": "forbid"}
