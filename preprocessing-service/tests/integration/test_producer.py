import pytest

from messaging.models import EventEnvelope, PdfPreprocessingRequestedEvent
from messaging.producer.redis_producer import RedisProducer

pytestmark = pytest.mark.integration


def make_envelope():
    return EventEnvelope.create(
        event_type="PdfPreprocessingRequested",
        payload=PdfPreprocessingRequestedEvent(
            job_id="job-1", source_uri="s3://bucket/in/a.pdf"
        ),
        correlation_id="corr-1",
        source="test",
    )


async def test_publish_writes_one_message_with_event_field(app_settings, redis_client):
    """The field key must be 'event' — producer and consumer must agree on it."""
    producer = RedisProducer()
    env = make_envelope()

    message_id = await producer.publish(env)
    assert message_id

    entries = await redis_client.xrange(app_settings.STREAM_NAME)
    assert len(entries) == 1
    _, fields = entries[0]
    assert "event" in fields
    assert EventEnvelope.model_validate_json(fields["event"]).payload == env.payload

    await producer.close()


async def test_publish_to_an_explicit_stream_targets_that_stream(
    app_settings, redis_client
):
    """A handler publishes its follow-on event to OUTPUT_STREAM_NAME."""
    producer = RedisProducer()
    await producer.publish(make_envelope(), stream=app_settings.OUTPUT_STREAM_NAME)

    assert await redis_client.xlen(app_settings.STREAM_NAME) == 0
    assert await redis_client.xlen(app_settings.OUTPUT_STREAM_NAME) == 1

    await producer.close()
