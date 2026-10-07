"""Intended current contracts. Known defects live in test_known_gaps.py."""

import json
from dataclasses import asdict
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from config.settings import Settings
from core.detection import RestoreResult
from core.pipeline import PipelineResult
from core.s3 import normalize_s3_uri, suffix_uri
from messaging.adapters.legacy_redis_message_adapter import LegacyRedisMessageAdapter
from messaging.consumer.handlers import pdf_preprocessing_requested as handler
from messaging.consumer.redis_consumer import RedisConsumer
from messaging.models import EventEnvelope

FIXTURES = Path(__file__).parents[1] / "fixtures" / "contracts"


def load(name):
    return json.loads((FIXTURES / f"{name}-v1.json").read_text())


@pytest.mark.parametrize("name", ["typed-request", "typed-request-https"])
def test_current_typed_request_identity_and_roundtrip(name):
    raw = load(name)
    envelope = EventEnvelope.model_validate(raw)
    assert str(envelope.event_id) == raw["event_id"]
    assert envelope.correlation_id == raw["correlation_id"]
    assert envelope.traceparent == raw["traceparent"]
    assert envelope.schema_version == "1.0.0"
    assert envelope.payload.model_dump() == raw["payload"]
    assert set(raw["payload"]) == {"job_id", "source_uri", "legacy_payload"}
    assert EventEnvelope.model_validate_json(envelope.model_dump_json()) == envelope


def test_pre_detector_request_fixture_remains_accepted():
    raw = load("typed-request")
    del raw["payload"]["legacy_payload"]
    assert EventEnvelope.model_validate(raw).payload.legacy_payload == {}


@pytest.mark.parametrize("kind", ["clean", "restored"])
def test_current_typed_completion_accepts_detector_contract(kind):
    raw = load(f"typed-completion-{kind}")
    envelope = EventEnvelope.model_validate(raw)
    assert envelope.payload.model_dump(mode="json") == raw["payload"]
    assert envelope.event_type == "PdfPreprocessingCompleted"
    assert envelope.schema_version == "1.0.0"
    assert isinstance(envelope.event_id, UUID)
    if kind == "restored":
        assert envelope.payload.detectors["clip_hidden_text"].spans_restored == 1
        assert envelope.payload.detectors["clip_hidden_text"].pages_affected == 1
    else:
        assert envelope.payload.detectors == {}
        assert envelope.payload.output_uri is None


@pytest.mark.parametrize("bytes_values", [False, True])
def test_legacy_request_adapts_logical_identity_and_safe_fields(bytes_values):
    raw = load("legacy-request")
    fields = {k: v.encode() for k, v in raw.items()} if bytes_values else raw
    envelope = LegacyRedisMessageAdapter().adapt(fields)
    assert envelope.payload.job_id == raw["jobid"]
    assert envelope.payload.source_uri == raw["s3filepath"]
    assert envelope.payload.legacy_payload == raw
    assert envelope.correlation_id == raw["jobid"]
    assert envelope.event_type == "PdfPreprocessingRequested"
    assert isinstance(envelope.event_id, UUID)
    # Deliberately do not require regenerated IDs or missing trace propagation.


def test_pipeline_result_serialization_includes_detector_results():
    detector = RestoreResult(True, 1, 1, True)
    result = PipelineResult(True, 1, 1, True, {"clip_hidden_text": detector})
    assert asdict(result) == {
        "hidden_found": True,
        "spans_restored": 1,
        "pages_affected": 1,
        "wrote_output": True,
        "detectors": {"clip_hidden_text": asdict(detector)},
    }


@pytest.mark.parametrize(
    "uri",
    [
        "s3://synthetic-bucket/docs/input.pdf",
        "https://store.invalid/synthetic-bucket/docs/input.pdf",
    ],
)
def test_ordinary_object_identity_and_suffix(uri, monkeypatch):
    monkeypatch.setattr(
        "core.s3.get_settings",
        lambda: Settings(_env_file=None, S3_ENDPOINT_URL="https://store.invalid"),
    )
    canonical = normalize_s3_uri(uri)
    assert canonical == "s3://synthetic-bucket/docs/input.pdf"
    assert suffix_uri(canonical, "PREPROCESSED") == (
        "s3://synthetic-bucket/docs/inputPREPROCESSED.pdf"
    )


class MemoryState:
    def __init__(self):
        self.outcomes = {}

    async def hsetnx(self, key, field, value):
        if key in self.outcomes:
            return False
        self.outcomes[key] = value
        return True

    async def hset(self, *args, **kwargs):
        pass

    async def expire(self, *args, **kwargs):
        pass


@pytest.fixture
def handler_boundary(monkeypatch, tmp_path):
    """Cheap serialization boundary, not another PDF/Redis integration harness."""
    settings = Settings(
        _env_file=None, WORK_DIR=str(tmp_path), S3_ENDPOINT_URL="https://store.invalid"
    )
    monkeypatch.setattr(handler, "get_settings", lambda: settings)
    monkeypatch.setattr("core.s3.get_settings", lambda: settings)
    monkeypatch.setattr(handler, "fetch_pdf", AsyncMock())
    monkeypatch.setattr(handler, "upload_pdf", AsyncMock())
    state = MemoryState()
    monkeypatch.setattr(handler, "get_state_client", lambda: state)
    producer = AsyncMock()
    monkeypatch.setattr(handler, "get_producer", lambda: producer)
    return producer


@pytest.mark.parametrize("dialect", ["typed", "legacy"])
@pytest.mark.parametrize("restored", [False, True])
async def test_handler_emits_supported_completion_fields(
    handler_boundary, monkeypatch, dialect, restored
):
    detector = RestoreResult(restored, int(restored), int(restored), restored)
    result = PipelineResult(
        restored, int(restored), int(restored), restored, {"clip_hidden_text": detector}
    )
    monkeypatch.setattr(handler, "run_pipeline", lambda *args: result)
    request = (
        EventEnvelope.model_validate(load("typed-request"))
        if dialect == "typed"
        else LegacyRedisMessageAdapter().adapt(load("legacy-request"))
    )
    await handler.handle(request.payload, correlation_id=request.correlation_id)
    name = "restored" if restored else "clean"
    if dialect == "typed":
        envelope = handler_boundary.publish.call_args.args[0]
        expected = load("typed-completion-" + name)["payload"]
        actual = envelope.payload.model_dump(mode="json")
        actual.pop("completed_at")
        expected.pop("completed_at")
        assert actual == expected
        assert isinstance(envelope.event_id, UUID)
        assert envelope.correlation_id == request.correlation_id
        handler_boundary.publish_legacy.assert_not_called()
    else:
        actual = handler_boundary.publish_legacy.call_args.args[0]
        assert actual == load("legacy-completion-" + name)
        handler_boundary.publish.assert_not_called()
    assert handler.upload_pdf.await_count == int(restored)


async def test_typed_dlq_preserves_original_envelope_and_operational_identity(
    monkeypatch,
):
    redis = AsyncMock()
    monkeypatch.setattr(
        "messaging.consumer.redis_consumer.Redis.from_url", lambda *a, **k: redis
    )
    consumer = RedisConsumer()
    raw = json.dumps(load("typed-request"))
    await consumer._dead_letter(
        "1-0", {"event": raw}, "handler_error", "synthetic failure", 3
    )
    record = redis.xadd.call_args.kwargs["fields"]
    assert EventEnvelope.model_validate_json(
        record["event"]
    ) == EventEnvelope.model_validate_json(raw)
    assert record["original_message_id"] == "1-0"
    assert record["original_stream"] == consumer.stream_name
    assert record["reason"] == "handler_error"
    assert record["delivery_count"] == "3"
    # No assertion requiring raw error text, payload leaks or missing legacy data.


def test_contract_fixtures_are_explicitly_synthetic_and_not_signed():
    corpus = "\n".join(p.read_text() for p in FIXTURES.glob("*.json"))
    assert "synthetic" in corpus
    for forbidden in ("gov.bc.ca", "amazonaws.com", "?sig=", "usertoken", "password"):
        assert forbidden not in corpus
