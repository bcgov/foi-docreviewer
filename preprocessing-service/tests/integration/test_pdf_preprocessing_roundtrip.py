from pathlib import Path

import pytest

import cli
from messaging.consumer.handlers import pdf_preprocessing_requested as handler_mod
from messaging.consumer.redis_consumer import RedisConsumer
from messaging.models import EventEnvelope
from messaging.producer.redis_producer import close_producer
from messaging.state import close_state_client
from tests.pdf_helpers import make_pdf

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
async def _close_clients(app_settings):
    yield
    await close_state_client()
    await close_producer()


async def _drain(consumer, passes=3):
    for _ in range(passes):
        response = await consumer.redis.xreadgroup(
            groupname=consumer.consumer_group,
            consumername=consumer.consumer_name,
            streams={consumer.stream_name: ">"},
            count=10,
            block=500,
        )
        for _stream, messages in response or []:
            for message_id, fields in messages:
                await consumer._handle_one(message_id, fields)


async def test_cli_publish_flows_through_fetch_restore_upload_publish(
    app_settings, redis_client, tmp_path, monkeypatch
):
    """
    CLI publishes PdfPreprocessingRequested twice; the worker fetches +
    restores + uploads once and publishes exactly one PdfPreprocessingCompleted
    on the output stream. Two in, one out.
    """
    monkeypatch.setattr(app_settings, "WORK_DIR", str(tmp_path / "work"))
    uploads = []

    async def fake_fetch(source_uri: str, dst) -> Path:
        return make_pdf(dst, clip=True)

    async def fake_upload(src, dest_uri: str) -> str:
        uploads.append(dest_uri)
        return dest_uri

    monkeypatch.setattr(handler_mod, "fetch_pdf", fake_fetch)
    monkeypatch.setattr(handler_mod, "upload_pdf", fake_upload)

    args = cli.build_parser().parse_args(
        [
            "publish",
            "--source-uri",
            "s3://in-bucket/incoming/x.pdf",
            "--job-id",
            "demo-1",
            "--count",
            "2",
        ]
    )
    await cli.publish(args)

    consumer = RedisConsumer()
    await consumer.ensure_group()
    await _drain(consumer)
    await consumer.close()

    assert uploads == ["s3://in-bucket/incoming/xPREPROCESSED.pdf"]

    state = await redis_client.hgetall("preprocessing:demo-1")
    assert state["outcome"] == "text_restored"

    completed = await redis_client.xrange(app_settings.OUTPUT_STREAM_NAME)
    assert len(completed) == 1
    env = EventEnvelope.model_validate_json(completed[0][1]["event"])
    assert env.event_type == "PdfPreprocessingCompleted"
    assert env.payload.job_id == "demo-1"
    assert env.payload.output_uri == uploads[0]

    pending = await redis_client.xpending(
        app_settings.STREAM_NAME, app_settings.CONSUMER_GROUP
    )
    assert pending["pending"] == 0
    assert await redis_client.xlen(app_settings.dlq_stream) == 0
