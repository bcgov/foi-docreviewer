"""Unit tests for adapting legacy Redis fields into preprocessing requests."""

import json

import pytest

from messaging.adapters.legacy_redis_message_adapter import LegacyRedisMessageAdapter


def legacy_fields():
    return {
        "jobid": "42",
        "s3filepath": "s3://bucket/input.pdf",
        "filename": "input.pdf",
        "ministryrequestid": "7",
        "documentmasterid": "9",
        "trigger": "recordupload",
        "createdby": "user@example.com",
        "requestnumber": "REQ-1",
        "batch": "batch-1",
        "incompatible": "false",
        "bcgovcode": "EDU",
        "attributes": json.dumps({"isattachment": True}),
        "usertoken": "token",
        "documentid": "11",
        "outputdocumentmasterid": "12",
        "originaldocumentmasterid": "13",
        "compresseds3filepath": "s3://bucket/compressed.pdf",
    }


def test_adapt_preserves_all_legacy_fields():
    fields = legacy_fields()

    envelope = LegacyRedisMessageAdapter().adapt(fields)

    assert envelope.event_type == "PdfPreprocessingRequested"
    assert envelope.correlation_id == "42"
    assert envelope.payload.job_id == "42"
    assert envelope.payload.source_uri == "s3://bucket/input.pdf"
    assert envelope.payload.legacy_payload == fields


@pytest.mark.parametrize("missing", ["jobid", "s3filepath"])
def test_adapt_rejects_missing_required_legacy_fields(missing):
    fields = legacy_fields()
    del fields[missing]

    with pytest.raises(ValueError, match=missing):
        LegacyRedisMessageAdapter().adapt(fields)
