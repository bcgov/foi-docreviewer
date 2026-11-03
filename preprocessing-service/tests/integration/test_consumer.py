# tests/integration/test_consumer.py

import asyncio

import pytest

from messaging.consumer import RedisConsumer, dispatcher
from messaging.models import EventEnvelope, PdfPreprocessingRequestedEvent
from messaging.producer.redis_producer import RedisProducer

pytestmark = pytest.mark.integration


def make_envelope(job_id="job-1"):
    return EventEnvelope.create(
        event_type="PdfPreprocessingRequested",
        payload=PdfPreprocessingRequestedEvent(
            job_id=job_id, source_uri="s3://bucket/in/a.pdf"
        ),
        correlation_id="corr-1",
        source="test",
    )


async def _drain(consumer, timeout=5.0):
    """Run the consumer until it has acked everything or the timeout expires."""
    task = asyncio.create_task(consumer.start())
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        await asyncio.sleep(0.1)
        pending = await consumer.redis.xpending(
            consumer.stream_name, consumer.consumer_group
        )
        if pending["pending"] == 0:
            break
    await consumer.stop()
    await asyncio.wait_for(task, timeout=5)


async def test_valid_message_is_handled_and_acked(
    app_settings, redis_client, monkeypatch
):
    seen = []

    async def fake_handle(payload, *, correlation_id):
        seen.append(payload.job_id)

    monkeypatch.setitem(dispatcher.HANDLERS, "PdfPreprocessingRequested", fake_handle)

    producer = RedisProducer()
    consumer = RedisConsumer(consumer_name="test-1")
    await consumer.ensure_group()
    await producer.publish(make_envelope("job-1"))

    await _drain(consumer)

    assert seen == ["job-1"]
    pending = await redis_client.xpending(
        app_settings.STREAM_NAME, app_settings.CONSUMER_GROUP
    )
    assert pending["pending"] == 0
    assert await redis_client.xlen(app_settings.dlq_stream) == 0

    await producer.close()
    await consumer.close()


async def test_failing_handler_retries_then_dead_letters(
    app_settings, redis_client, monkeypatch
):
    attempts = []

    async def always_fails(payload, *, correlation_id):
        attempts.append(1)
        raise RuntimeError("handler exploded")

    monkeypatch.setitem(dispatcher.HANDLERS, "PdfPreprocessingRequested", always_fails)

    producer = RedisProducer()
    consumer = RedisConsumer(consumer_name="test-2")
    await consumer.ensure_group()
    await producer.publish(make_envelope("job-2"))

    await _drain(consumer)

    assert len(attempts) == app_settings.CONSUMER_MAX_RETRIES
    dlq = await redis_client.xrange(app_settings.dlq_stream)
    assert len(dlq) == 1
    _, fields = dlq[0]
    assert "handler exploded" in fields["error"]
    assert "event" in fields
    # Original left the pending list.
    pending = await redis_client.xpending(
        app_settings.STREAM_NAME, app_settings.CONSUMER_GROUP
    )
    assert pending["pending"] == 0

    await producer.close()
    await consumer.close()


async def test_malformed_envelope_goes_straight_to_the_dlq(app_settings, redis_client):
    """A message that cannot parse will never parse; retrying is pointless."""
    consumer = RedisConsumer(consumer_name="test-3")
    await consumer.ensure_group()
    await redis_client.xadd(app_settings.STREAM_NAME, {"event": "{not json"})

    await _drain(consumer)

    dlq = await redis_client.xrange(app_settings.dlq_stream)
    assert len(dlq) == 1
    assert dlq[0][1]["reason"] == "validation_error"

    await consumer.close()
