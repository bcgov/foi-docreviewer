import json
import os
import sys
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from rstreamio.compressionevents import (
    CompressionEventDefinition,
    StandardCompressionPublisher,
)


class RecordingRedis:
    def __init__(self, stream_id=b"1712345678901-0"):
        self.stream_id = stream_id
        self.calls = []

    def xadd(self, stream, fields):
        self.calls.append((stream, fields))
        return self.stream_id


def publisher(redis, uuids=("event-uuid", "correlation-uuid")):
    values = iter(uuids)
    definition = CompressionEventDefinition(
        topic="compression",
        event_type="document.compression.requested",
        schema_version="1.0.0",
        source="foi-docreviewer.dedupe",
    )
    return StandardCompressionPublisher(
        redis,
        "foi",
        definition,
        uuid_provider=lambda: next(values),
        now_provider=lambda: datetime(2026, 8, 18, 12, 34, 56, 123456, tzinfo=timezone.utc),
    )


def test_publish_writes_the_exact_standard_envelope_and_watermill_fields():
    redis = RecordingRedis()
    payload = valid_payload()
    result = publisher(redis).publish(payload)

    assert result.stream_id == b"1712345678901-0"
    assert result.event_id == "event-uuid"
    assert result.correlation_id == "correlation-uuid"
    assert result.timestamp == "2026-08-18T12:34:56.123456Z"
    assert len(redis.calls) == 1
    stream, fields = redis.calls[0]
    assert stream == "foi:compression"
    assert fields["_watermill_message_uuid"] == "event-uuid"
    assert fields["metadata"] == b""
    assert fields["payload"] == (
        b'{"event_id":"event-uuid","event_type":"document.compression.requested",'
        b'"schema_version":"1.0.0","source":"foi-docreviewer.dedupe",'
        b'"timestamp":"2026-08-18T12:34:56.123456Z",'
        b'"correlation_id":"correlation-uuid",'
        b'"payload":{"jobid":5199,"s3filepath":"s3://bucket/input.pdf",'
        b'"filename":"input.pdf","ministryrequestid":42,"documentmasterid":7,'
        b'"trigger":"new","createdby":"user@example.com","requestnumber":"LDB-123",'
        b'"batch":"batch-1","incompatible":false,"bcgovcode":"LDB",'
        b'"attributes":{"isattachment":true,"pages":3}}}'
    )


def test_publish_uses_a_provided_correlation_id_without_consuming_another_uuid():
    redis = RecordingRedis("1712345678902-0")
    result = publisher(redis, uuids=("event-uuid",)).publish(
        valid_payload(), correlation_id="request-123"
    )

    assert result.correlation_id == "request-123"
    envelope = json.loads(redis.calls[0][1]["payload"])
    assert envelope["event_id"] == "event-uuid"
    assert envelope["correlation_id"] == "request-123"


@pytest.mark.parametrize("correlation_id", ["", " ", 1, False])
def test_publish_rejects_empty_or_non_string_correlation_ids(correlation_id):
    redis = RecordingRedis()

    with pytest.raises(ValueError, match="correlation_id must be a non-empty string"):
        publisher(redis, uuids=("event-uuid",)).publish(
            valid_payload(),
            correlation_id=correlation_id,
        )

    assert redis.calls == []


@pytest.mark.parametrize(
    "stream_prefix, definition",
    [
        ("", CompressionEventDefinition("compression", "event", "1.0.0", "source")),
        ("foi", CompressionEventDefinition("", "event", "1.0.0", "source")),
        ("foi", CompressionEventDefinition("compression", "", "1.0.0", "source")),
        ("foi", CompressionEventDefinition("compression", "event", "", "source")),
        ("foi", CompressionEventDefinition("compression", "event", "1.0.0", "")),
    ],
)
def test_publish_rejects_empty_stream_or_event_definition_values(stream_prefix, definition):
    with pytest.raises(ValueError):
        StandardCompressionPublisher(
            RecordingRedis(),
            stream_prefix,
            definition,
            uuid_provider=lambda: "uuid",
            now_provider=lambda: datetime.now(timezone.utc),
        )


def test_publish_propagates_redis_failures_without_walrus_fallback():
    class FailingRedis:
        def xadd(self, stream, fields):
            raise TimeoutError("redis unavailable")

    with pytest.raises(TimeoutError, match="redis unavailable"):
        publisher(FailingRedis()).publish(valid_payload())


def test_publish_rejects_naive_datetimes():
    redis = RecordingRedis()
    standard_publisher = StandardCompressionPublisher(
        redis,
        "foi",
        CompressionEventDefinition(
            "compression",
            "document.compression.requested",
            "1.0.0",
            "foi-docreviewer.dedupe",
        ),
        uuid_provider=lambda: "uuid",
        now_provider=lambda: datetime(2026, 8, 18, 12, 34, 56),
    )

    with pytest.raises(ValueError, match="timezone-aware"):
        standard_publisher.publish(valid_payload(), correlation_id="request-123")

    assert redis.calls == []


def test_publish_does_not_use_a_walrus_dependency_or_fallback(monkeypatch):
    monkeypatch.setitem(sys.modules, "walrus", None)
    redis = RecordingRedis()

    publisher(redis).publish(valid_payload())

    assert len(redis.calls) == 1


def valid_payload(**overrides):
    payload = {
        "jobid": 5199,
        "s3filepath": "s3://bucket/input.pdf",
        "filename": "input.pdf",
        "ministryrequestid": 42,
        "documentmasterid": 7,
        "trigger": "new",
        "createdby": "user@example.com",
        "requestnumber": "LDB-123",
        "batch": "batch-1",
        "incompatible": False,
        "bcgovcode": "LDB",
        "attributes": {"isattachment": True, "pages": 3},
    }
    payload.update(overrides)
    return payload


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (valid_payload(jobid="5199"), "payload.jobid must be an integer"),
        (valid_payload(documentmasterid=True), "payload.documentmasterid must be an integer"),
        (valid_payload(incompatible="false"), "payload.incompatible must be a boolean"),
        (valid_payload(attributes='{"pages": 3}'), "payload.attributes must be an object"),
        (valid_payload(documentid="8"), "payload.documentid must be an integer"),
        (valid_payload(usertoken=1), "payload.usertoken must be a string"),
        ({key: value for key, value in valid_payload().items() if key != "filename"}, "payload.filename is required"),
    ],
)
def test_publish_rejects_missing_or_wrongly_typed_compression_payload_fields(payload, message):
    redis = RecordingRedis()

    with pytest.raises(ValueError, match=message):
        publisher(redis).publish(payload)

    assert redis.calls == []


@pytest.mark.parametrize(
    "definition",
    [
        CompressionEventDefinition("compression", "document.other", "1.0.0", "foi-docreviewer.dedupe"),
        CompressionEventDefinition("compression", "document.compression.requested", "1.0", "foi-docreviewer.dedupe"),
        CompressionEventDefinition("compression", "document.compression.requested", "1.0.0", "dedupe"),
    ],
)
def test_standard_publisher_rejects_non_contract_event_definitions(definition):
    with pytest.raises(ValueError):
        StandardCompressionPublisher(RecordingRedis(), "foi", definition)
