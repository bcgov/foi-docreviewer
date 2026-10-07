"""Desired invariants, not passing assertions that require defects to remain."""

import json
from unittest.mock import AsyncMock

import pytest

from config.settings import Settings
from core.pipeline import PipelineResult
from core.s3 import normalize_s3_uri
from messaging.consumer.handlers import pdf_preprocessing_requested as handler
from messaging.consumer.redis_consumer import RedisConsumer
from messaging.models import PdfPreprocessingRequestedEvent
from tests.contract.test_current_contracts import MemoryState


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="Known URI gap: HTTPS encoded-space key must retain object identity",
)
def test_https_encoded_space_resolves_to_actual_object_key(monkeypatch):
    monkeypatch.setattr(
        "core.s3.get_settings",
        lambda: Settings(_env_file=None, S3_ENDPOINT_URL="https://store.invalid"),
    )
    assert normalize_s3_uri("https://store.invalid/synthetic/docs/a%20b.pdf") == (
        "s3://synthetic/docs/a b.pdf"
    )


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="Known DLQ gap: legacy failure needs replayable safe logical fields",
)
async def test_legacy_dlq_retains_safe_replay_identity(monkeypatch):
    redis = AsyncMock()
    monkeypatch.setattr(
        "messaging.consumer.redis_consumer.Redis.from_url", lambda *a, **k: redis
    )
    consumer = RedisConsumer()
    fields = {
        "jobid": "synthetic-job",
        "s3filepath": "s3://synthetic/input.pdf",
        "usertoken": "SYNTH_CREDENTIAL",
    }
    await consumer._dead_letter(
        "1-0", fields, "handler_error", "SYNTH_EXCEPTION_TEXT", 3
    )
    record = redis.xadd.call_args.kwargs["fields"]
    # Accept either existing envelope or a safe original-fields representation;
    # the future contract owner still chooses the precise DLQ storage schema.
    retained = record.get("fields") or record.get("event")
    assert retained, "no self-contained logical request retained"
    decoded = json.loads(retained) if isinstance(retained, str) else retained
    request = decoded.get("payload", decoded)
    assert request.get("jobid", request.get("job_id")) == "synthetic-job"
    assert (
        request.get("s3filepath", request.get("source_uri"))
        == "s3://synthetic/input.pdf"
    )
    serialized = json.dumps(record)
    assert "SYNTH_CREDENTIAL" not in serialized
    assert "SYNTH_EXCEPTION_TEXT" not in serialized


@pytest.mark.parametrize("dialect", ["typed", "legacy"])
@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="Known publication gap: completion must survive first failure and replay",
)
async def test_completion_recovers_after_publication_failure(
    monkeypatch, tmp_path, dialect
):
    monkeypatch.setattr(
        handler,
        "get_settings",
        lambda: Settings(_env_file=None, WORK_DIR=str(tmp_path)),
    )
    monkeypatch.setattr(handler, "fetch_pdf", AsyncMock())
    monkeypatch.setattr(handler, "upload_pdf", AsyncMock())
    monkeypatch.setattr(
        handler, "run_pipeline", lambda *a: PipelineResult(False, 0, 0, False)
    )
    state = MemoryState()
    monkeypatch.setattr(handler, "get_state_client", lambda: state)
    completions = []
    attempted_ids = []

    async def publish(payload, **kwargs):
        attempted_ids.append(getattr(payload, "event_id", None))
        if len(attempted_ids) == 1:
            raise RuntimeError("synthetic first publish failure")
        completions.append(payload)

    producer = AsyncMock()
    producer.publish.side_effect = publish
    producer.publish_legacy.side_effect = publish
    monkeypatch.setattr(handler, "get_producer", lambda: producer)
    legacy = {"jobid": "synthetic-job", "s3filepath": "s3://synthetic/input.pdf"}
    request = PdfPreprocessingRequestedEvent(
        job_id="synthetic-job",
        source_uri="s3://synthetic/input.pdf",
        legacy_payload=legacy if dialect == "legacy" else {},
    )
    # Intentionally v1-boundary-specific: future durable publication work should
    # migrate this invariant to eventual publication, stable completion identity,
    # and no lost accepted job at the outbox/publisher boundary, without requiring
    # synchronous handler exception propagation. Keep strict xfail until that
    # migration is reviewed.
    with pytest.raises(RuntimeError, match="synthetic first publish failure"):
        await handler.handle(request, correlation_id="synthetic-correlation")
    await handler.handle(request, correlation_id="synthetic-correlation")
    await handler.handle(request, correlation_id="synthetic-correlation")
    assert len(completions) == 1, "durable completion intent was lost"
    if dialect == "typed":
        assert (
            len(set(attempted_ids)) == 1
        ), "completion identity changed across attempts"
