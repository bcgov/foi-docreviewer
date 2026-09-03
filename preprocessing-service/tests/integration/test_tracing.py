from pathlib import Path

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.util._once import Once

from messaging.consumer.handlers import pdf_preprocessing_requested as handler_mod
from messaging.consumer.redis_consumer import RedisConsumer
from messaging.models import EventEnvelope, PdfPreprocessingRequestedEvent
from messaging.producer.redis_producer import RedisProducer, close_producer
from messaging.state import close_state_client
from tests.pdf_helpers import make_pdf

pytestmark = pytest.mark.integration

SOURCE_URI = "s3://in-bucket/incoming/a.pdf"


@pytest.fixture(scope="session")
def span_exporter():
    """Attach an in-memory exporter to whatever TracerProvider is live."""
    provider = trace.get_tracer_provider()
    if not isinstance(provider, TracerProvider):
        trace._TRACER_PROVIDER = None
        trace._TRACER_PROVIDER_SET_ONCE = Once()
        provider = TracerProvider()
        trace.set_tracer_provider(provider)

    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return exporter


@pytest.fixture
def spans(span_exporter):
    span_exporter.clear()
    yield span_exporter
    span_exporter.clear()


@pytest.fixture(autouse=True)
async def _close_clients(app_settings):
    yield
    await close_state_client()
    await close_producer()


@pytest.fixture
def s3_stub(tmp_path, app_settings, monkeypatch):
    monkeypatch.setattr(app_settings, "WORK_DIR", str(tmp_path / "work"))

    async def fake_fetch(source_uri: str, dst) -> Path:
        return make_pdf(dst, clip=True)

    async def fake_upload(src, dest_uri: str) -> str:
        return dest_uri

    monkeypatch.setattr(handler_mod, "fetch_pdf", fake_fetch)
    monkeypatch.setattr(handler_mod, "upload_pdf", fake_upload)


def by_name(exporter, name):
    return [s for s in exporter.get_finished_spans() if s.name == name]


async def test_publish_injects_traceparent_into_the_envelope(
    app_settings, redis_client, spans
):
    producer = RedisProducer()
    await producer.publish(
        EventEnvelope.create(
            event_type="PdfPreprocessingRequested",
            payload=PdfPreprocessingRequestedEvent(
                job_id="job-1", source_uri=SOURCE_URI
            ),
            correlation_id="corr-1",
            source="test",
        )
    )
    await producer.close()

    entries = await redis_client.xrange(app_settings.STREAM_NAME)
    published = EventEnvelope.model_validate_json(entries[0][1]["event"])

    assert published.traceparent is not None
    publish_span = by_name(spans, "publish PdfPreprocessingRequested")[0]
    assert format(publish_span.context.trace_id, "032x") in published.traceparent


async def test_the_chain_is_one_trace_from_cli_to_the_completed_event(
    app_settings, redis_client, spans, s3_stub
):
    """
    cli.publish -> publish PdfPreprocessingRequested -> consume it ->
    publish PdfPreprocessingCompleted, all one trace, each span parented to the
    one before.
    """
    tracer = trace.get_tracer("test")
    producer = RedisProducer()
    with tracer.start_as_current_span("cli.publish"):
        await producer.publish(
            EventEnvelope.create(
                event_type="PdfPreprocessingRequested",
                payload=PdfPreprocessingRequestedEvent(
                    job_id="job-1", source_uri=SOURCE_URI
                ),
                correlation_id="job-1",
                source="cli",
            )
        )

    consumer = RedisConsumer()
    await consumer.ensure_group()
    response = await consumer.redis.xreadgroup(
        groupname=consumer.consumer_group,
        consumername=consumer.consumer_name,
        streams={consumer.stream_name: ">"},
        count=10,
        block=1000,
    )
    for _stream, messages in response or []:
        for message_id, fields in messages:
            await consumer._handle_one(message_id, fields)
    await consumer.close()

    root = by_name(spans, "cli.publish")[0]
    publish_req = by_name(spans, "publish PdfPreprocessingRequested")[0]
    consume_req = by_name(spans, "consume PdfPreprocessingRequested")[0]
    publish_done = by_name(spans, "publish PdfPreprocessingCompleted")[0]

    trace_id = root.context.trace_id
    assert consume_req.context.trace_id == trace_id
    assert publish_done.context.trace_id == trace_id

    assert consume_req.parent.span_id == publish_req.context.span_id
    assert publish_done.parent.span_id == consume_req.context.span_id


async def test_an_envelope_without_traceparent_starts_a_new_trace(
    app_settings, redis_client, spans, s3_stub
):
    consumer = RedisConsumer()
    await consumer.ensure_group()

    envelope = EventEnvelope.create(
        event_type="PdfPreprocessingRequested",
        payload=PdfPreprocessingRequestedEvent(job_id="job-2", source_uri=SOURCE_URI),
        correlation_id="corr-2",
        source="test",
    )
    assert envelope.traceparent is None

    await consumer._handle_one("1-1", {"event": envelope.model_dump_json()})
    await consumer.close()

    span = by_name(spans, "consume PdfPreprocessingRequested")[0]
    assert span.parent is None
