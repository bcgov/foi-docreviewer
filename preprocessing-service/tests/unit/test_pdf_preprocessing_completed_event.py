"""Unit tests for the completion event schema."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from messaging.models import PdfPreprocessingCompletedEvent


def _event_kwargs(**overrides):
    values = {
        "job_id": "job-1",
        "outcome": "text_restored",
        "spans_restored": 2,
        "pages_affected": 1,
        "output_uri": "s3://bucket/key.pdf",
        "completed_at": datetime.now(UTC),
    }
    values.update(overrides)
    return values


def test_detectors_default_to_empty():
    event = PdfPreprocessingCompletedEvent(**_event_kwargs())

    assert event.detectors == {}


def test_detectors_round_trip():
    event = PdfPreprocessingCompletedEvent(
        **_event_kwargs(
            detectors={"clip_hidden_text": {"spans_restored": 2, "pages_affected": 1}}
        )
    )

    assert event.detectors["clip_hidden_text"].spans_restored == 2


def test_detector_outcome_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        PdfPreprocessingCompletedEvent(
            **_event_kwargs(
                detectors={
                    "clip_hidden_text": {
                        "spans_restored": 2,
                        "pages_affected": 1,
                        "unexpected": "value",
                    }
                }
            )
        )
