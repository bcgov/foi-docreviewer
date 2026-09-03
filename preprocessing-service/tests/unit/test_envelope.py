from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from messaging.models import (
    EventEnvelope,
    PdfPreprocessingCompletedEvent,
    PdfPreprocessingRequestedEvent,
)


def make_requested(job_id="job-1"):
    return PdfPreprocessingRequestedEvent(
        job_id=job_id, source_uri="s3://bucket/in/a.pdf"
    )


def test_create_builds_valid_envelope():
    env = EventEnvelope.create(
        event_type="PdfPreprocessingRequested",
        payload=make_requested(),
        correlation_id="corr-1",
        source="cli",
    )
    assert env.event_type == "PdfPreprocessingRequested"
    assert env.schema_version == "1.0.0"
    assert env.payload.job_id == "job-1"
    assert env.event_id is not None


def test_envelope_round_trips_through_json():
    env = EventEnvelope.create(
        event_type="PdfPreprocessingRequested",
        payload=make_requested("job-2"),
        correlation_id="corr-2",
        source="cli",
    )
    restored = EventEnvelope.model_validate_json(env.model_dump_json())
    assert restored.payload == env.payload
    assert restored.event_id == env.event_id


def test_unknown_event_type_is_rejected():
    with pytest.raises(ValidationError):
        EventEnvelope.create(
            event_type="Nonsense",
            payload=make_requested(),
            correlation_id="c",
            source="cli",
        )


def test_extra_fields_are_forbidden():
    env = EventEnvelope.create(
        event_type="PdfPreprocessingRequested",
        payload=make_requested(),
        correlation_id="corr-4",
        source="cli",
    )
    payload = env.model_dump(mode="json")
    payload["surprise"] = 1

    with pytest.raises(ValidationError):
        EventEnvelope.model_validate(payload)


def test_completed_envelope_round_trips_to_the_right_payload_type():
    """
    EventPayload is a union. Pydantic must resolve a serialised
    PdfPreprocessingCompleted back to its own type, not coerce it into the
    first member of the union.
    """
    env = EventEnvelope.create(
        event_type="PdfPreprocessingCompleted",
        payload=PdfPreprocessingCompletedEvent(
            job_id="job-1",
            outcome="text_restored",
            spans_restored=24,
            pages_affected=6,
            output_uri="s3://out-bucket/preprocessed/job-1.pdf",
            completed_at=datetime.now(UTC),
        ),
        correlation_id="corr-1",
        source="pdf-preprocessing",
    )

    parsed = EventEnvelope.model_validate_json(env.model_dump_json())

    assert isinstance(parsed.payload, PdfPreprocessingCompletedEvent)
    assert parsed.payload.spans_restored == 24
    assert parsed.payload.outcome == "text_restored"


def test_completed_outcome_is_constrained():
    with pytest.raises(ValidationError):
        PdfPreprocessingCompletedEvent(
            job_id="job-1",
            outcome="banana",
            spans_restored=0,
            pages_affected=0,
            completed_at=datetime.now(UTC),
        )


def test_traceparent_is_optional_and_survives_the_round_trip():
    env = EventEnvelope.create(
        event_type="PdfPreprocessingRequested",
        payload=make_requested(),
        correlation_id="corr-1",
        source="cli",
    )
    assert env.traceparent is None

    tp = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"
    env = env.model_copy(update={"traceparent": tp})
    assert EventEnvelope.model_validate_json(env.model_dump_json()).traceparent == tp
