import json
import logging
import os
import sys
from types import SimpleNamespace

import pytest
import redis

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# The package initializer eagerly imports the database helper, although these
# producer unit tests do not exercise a database connection.
psycopg2 = sys.modules.setdefault("psycopg2", SimpleNamespace(connect=lambda **kwargs: None))
psycopg2.sql = SimpleNamespace(SQL=lambda query: query)
psycopg2.DatabaseError = Exception

import services.compressionproducerservice as producer_module
from rstreamio.compressionevents import PublishResult
from utils.loggingutils import configure_logging


class FakeStream:
    def __init__(self):
        self.calls = []

    def add(self, fields, id):
        self.calls.append((fields, id))
        return "1712345678901-0"


class FakeDatabase:
    instances = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.stream = FakeStream()
        self.instances.append(self)

    def Stream(self, name):
        self.stream_name = name
        return self.stream


class RecordingLegacyPublisher:
    instances = []

    def __init__(self, stream):
        self.stream = stream
        self.payloads = []
        self.instances.append(self)

    def publish(self, payload):
        self.payloads.append(payload)
        return "1712345678901-0"


class RecordingStandardPublisher:
    instances = []

    def __init__(self, redis_client, stream_prefix, event_definition):
        self.redis_client = redis_client
        self.stream_prefix = stream_prefix
        self.event_definition = event_definition
        self.calls = []
        self.instances.append(self)

    def publish(self, payload, correlation_id=None):
        self.calls.append((payload, correlation_id))
        return PublishResult(
            stream_id="1712345678901-0",
            event_id="event-123",
            correlation_id=correlation_id or "correlation-123",
            timestamp="2026-08-18T12:34:56Z",
        )


class RecordingRedis:
    instances = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.instances.append(self)


def source_message(**overrides):
    values = {
        "s3filepath": "s3://bucket/input.pdf",
        "filename": "input.pdf",
        "ministryrequestid": "42",
        "documentmasterid": "7",
        "trigger": "new",
        "createdby": "user@example.com",
        "requestnumber": "LDB-123",
        "batch": "batch-1",
        "incompatible": False,
        "usertoken": "super-secret-user-token",
        "bcgovcode": "LDB",
        "attributes": {"isattachment": True, "pages": 3},
        "documentid": None,
        "outputdocumentmasterid": None,
        "originaldocumentmasterid": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.fixture(autouse=True)
def configured_service(monkeypatch):
    FakeDatabase.instances = []
    RecordingLegacyPublisher.instances = []
    RecordingStandardPublisher.instances = []
    RecordingRedis.instances = []
    monkeypatch.setattr(producer_module, "compression_messaging_mode", "legacy", raising=False)
    monkeypatch.setattr(producer_module, "messaging_stream_prefix", "foi", raising=False)
    monkeypatch.setattr(producer_module, "compression_topic", "compression", raising=False)
    monkeypatch.setattr(producer_module, "compression_workload", "normal", raising=False)
    monkeypatch.setattr(producer_module, "compressionredishost", "redis-host", raising=False)
    monkeypatch.setattr(producer_module, "compressionredisport", "6379", raising=False)
    monkeypatch.setattr(producer_module, "compressionredispassword", "compression-password", raising=False)
    monkeypatch.setattr(producer_module, "compressionstreamkey", "legacy-compression", raising=False)
    monkeypatch.setattr(producer_module, "health_check_interval", "15", raising=False)
    monkeypatch.setattr(producer_module, "Database", FakeDatabase)
    monkeypatch.setattr(producer_module, "LegacyCompressionPublisher", RecordingLegacyPublisher, raising=False)
    monkeypatch.setattr(producer_module, "StandardCompressionPublisher", RecordingStandardPublisher, raising=False)
    monkeypatch.setattr(redis, "Redis", RecordingRedis)


def test_default_legacy_mode_constructs_only_the_legacy_adapter():
    producer = producer_module.compressionproducerservice()

    assert producer.mode == "legacy"
    assert len(FakeDatabase.instances) == 1
    assert len(RecordingLegacyPublisher.instances) == 1
    assert RecordingStandardPublisher.instances == []
    assert RecordingRedis.instances == []


def test_standard_mode_constructs_only_the_standard_adapter():
    producer_module.compression_messaging_mode = "standard"

    producer = producer_module.compressionproducerservice()

    assert producer.mode == "standard"
    assert FakeDatabase.instances == []
    assert RecordingLegacyPublisher.instances == []
    assert len(RecordingRedis.instances) == 1
    assert len(RecordingStandardPublisher.instances) == 1
    assert RecordingStandardPublisher.instances[0].stream_prefix == "foi"
    assert RecordingStandardPublisher.instances[0].event_definition.topic == "compression"
    assert RecordingStandardPublisher.instances[0].event_definition.event_type == "document.compression.requested"
    assert RecordingStandardPublisher.instances[0].event_definition.schema_version == "1.0.0"
    assert RecordingStandardPublisher.instances[0].event_definition.source == "foi-docreviewer.dedupe"


@pytest.mark.parametrize(
    "mode, host, port, prefix, topic, error",
    [
        ("unknown", "redis-host", "6379", "foi", "compression", "compression_messaging_mode"),
        ("legacy", None, "6379", "foi", "compression", "compressionredishost"),
        ("legacy", "redis-host", None, "foi", "compression", "compressionredisport"),
        ("legacy", "redis-host", "not-a-port", "foi", "compression", "compressionredisport"),
        ("standard", "redis-host", "0", "foi", "compression", "compressionredisport"),
        ("standard", "redis-host", "65536", "foi", "compression", "compressionredisport"),
        ("standard", "redis-host", "6379", None, "compression", "messaging_stream_prefix"),
        ("standard", "redis-host", "6379", "foi", None, "compression_topic"),
    ],
)
def test_initialization_rejects_invalid_mode_or_required_configuration(
    mode, host, port, prefix, topic, error
):
    producer_module.compression_messaging_mode = mode
    producer_module.compressionredishost = host
    producer_module.compressionredisport = port
    producer_module.messaging_stream_prefix = prefix
    producer_module.compression_topic = topic

    with pytest.raises(ValueError, match=error):
        producer_module.compressionproducerservice()


@pytest.mark.parametrize("workload", [None, "unexpected"])
def test_initialization_rejects_unset_or_invalid_compression_workload(workload):
    producer_module.compression_workload = workload

    with pytest.raises(ValueError, match="compression_workload"):
        producer_module.compressionproducerservice()


def test_compression_publish_log_is_safe_structured_json(capsys):
    producer_module.compression_messaging_mode = "standard"
    configure_logging()
    capsys.readouterr()

    producer = producer_module.compressionproducerservice()
    producer.producecompressionevent(source_message(), 11, correlation_id="request-123")

    records = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    record = next(record for record in records if record["event"] == "compression_published")

    assert record["stage"] == "foi:compression"
    assert record["stream_id"] == "1712345678901-0"
    assert record["event_id"] == "event-123"
    assert record["correlation_id"] == "request-123"
    assert record["job_id"] == 11
    assert record["document_master_id"] == 7
    assert "payload" not in record
    assert "usertoken" not in record
    assert "super-secret-user-token" not in json.dumps(record)
    assert "workload" not in RecordingStandardPublisher.instances[0].calls[0][0]
