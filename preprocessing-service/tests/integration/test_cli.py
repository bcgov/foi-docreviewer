import pytest

import cli
from messaging.models import EventEnvelope, PdfPreprocessingRequestedEvent
from messaging.producer.redis_producer import close_producer

pytestmark = pytest.mark.integration

URI = "s3://in-bucket/incoming/doc.pdf"


@pytest.fixture(autouse=True)
async def _close_clients(app_settings):
    yield
    await close_producer()


async def test_publish_writes_one_envelope_per_count(app_settings, redis_client):
    args = cli.build_parser().parse_args(
        ["publish", "--source-uri", URI, "--job-id", "demo-1", "--count", "2"]
    )

    job_id, message_ids = await cli.publish(args)

    assert job_id == "demo-1"
    assert len(message_ids) == 2
    entries = await redis_client.xrange(app_settings.STREAM_NAME)
    assert len(entries) == 2

    envelope = EventEnvelope.model_validate_json(entries[0][1]["event"])
    assert envelope.event_type == "PdfPreprocessingRequested"
    assert envelope.source == "cli"
    assert envelope.correlation_id == "demo-1"
    assert envelope.traceparent is not None
    assert isinstance(envelope.payload, PdfPreprocessingRequestedEvent)
    assert envelope.payload.source_uri == URI
    assert envelope.payload.job_id == "demo-1"


async def test_job_id_is_generated_when_omitted(app_settings, redis_client):
    args = cli.build_parser().parse_args(["publish", "--source-uri", URI])
    job_id, message_ids = await cli.publish(args)

    assert len(job_id) == 32  # uuid4().hex
    assert len(message_ids) == 1


def test_count_defaults_to_one():
    args = cli.build_parser().parse_args(["publish", "--source-uri", URI])
    assert args.count == 1


def test_zero_count_is_rejected_by_the_parser():
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["publish", "--source-uri", URI, "--count", "0"])


def test_source_uri_is_required():
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["publish", "--job-id", "x"])
