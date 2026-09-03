from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from messaging.models.events.pdf_preprocessing_completed import (
    PdfPreprocessingCompletedEvent,
)
from messaging.models.events.pdf_preprocessing_requested import (
    PdfPreprocessingRequestedEvent,
)

# Add your payload types to this union as the service grows.
EventPayload = PdfPreprocessingRequestedEvent | PdfPreprocessingCompletedEvent

SCHEMA_VERSION = "1.0.0"


class EventEnvelope(BaseModel):
    """
    The single validation boundary between services.

    Everything on the stream is an envelope; handlers only ever see a
    validated payload.
    """

    event_id: UUID
    event_type: Literal["PdfPreprocessingRequested", "PdfPreprocessingCompleted"]
    timestamp: datetime
    schema_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    correlation_id: str
    source: str

    # W3C trace context, injected by the producer from whatever span is
    # current and extracted by the consumer to parent its message span.
    # Optional: an envelope published outside a trace simply starts one.
    traceparent: str | None = None

    payload: EventPayload

    model_config = {"extra": "forbid"}

    @classmethod
    def create(
        cls,
        event_type: str,
        payload: EventPayload,
        correlation_id: str,
        source: str,
    ) -> "EventEnvelope":
        """Build an envelope, filling in id, timestamp and schema version."""
        return cls(
            event_id=uuid4(),
            event_type=event_type,
            timestamp=datetime.now(UTC),
            schema_version=SCHEMA_VERSION,
            correlation_id=correlation_id,
            source=source,
            payload=payload,
        )
