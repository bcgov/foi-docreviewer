from pathlib import Path

import pytest

from core.s3 import S3Error
from messaging.consumer.handlers import pdf_preprocessing_requested as handler_mod
from messaging.models import EventEnvelope, PdfPreprocessingRequestedEvent
from messaging.producer.redis_producer import close_producer
from messaging.state import close_state_client
from tests.pdf_helpers import SECRET, make_pdf

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
async def _close_clients(app_settings):
    yield
    await close_state_client()
    await close_producer()


@pytest.fixture
def s3_stub(tmp_path, app_settings, monkeypatch):
    """
    Fake core.s3: fetch writes a generated PDF to the work path, upload records
    the uploaded bytes and URI. Returns the uploads list.
    """
    monkeypatch.setattr(app_settings, "WORK_DIR", str(tmp_path / "work"))
    uploads: list[tuple[bytes, str]] = []
    state = {"clip": True}

    async def fake_fetch(source_uri: str, dst) -> Path:
        return make_pdf(dst, clip=state["clip"])

    async def fake_upload(src, dest_uri: str) -> str:
        uploads.append((Path(src).read_bytes(), dest_uri))
        return dest_uri

    monkeypatch.setattr(handler_mod, "fetch_pdf", fake_fetch)
    monkeypatch.setattr(handler_mod, "upload_pdf", fake_upload)
    return state, uploads


SOURCE_URI = "s3://in-bucket/incoming/a.pdf"
# <name>.pdf -> <name>PREPROCESSED.pdf, same bucket + prefix
EXPECTED_OUTPUT_URI = "s3://in-bucket/incoming/aPREPROCESSED.pdf"


def _payload(job_id):
    return PdfPreprocessingRequestedEvent(job_id=job_id, source_uri=SOURCE_URI)


async def test_hidden_text_is_restored_uploaded_and_completed_is_published(
    app_settings, redis_client, s3_stub
):
    _, uploads = s3_stub
    expected_uri = EXPECTED_OUTPUT_URI

    await handler_mod.handle(_payload("job-rec"), correlation_id="job-rec")

    # uploaded once, to the derived output key, with a real restored PDF
    assert len(uploads) == 1
    body, uri = uploads[0]
    assert uri == expected_uri
    import pymupdf

    assert SECRET in pymupdf.open(stream=body, filetype="pdf")[0].get_text()

    state = await redis_client.hgetall("preprocessing:job-rec")
    assert state["outcome"] == "text_restored"
    assert int(state["spans_restored"]) >= 1
    assert state["output_uri"] == expected_uri
    ttl = await redis_client.ttl("preprocessing:job-rec")
    assert 0 < ttl <= app_settings.STATE_TTL_SECONDS

    entries = await redis_client.xrange(app_settings.OUTPUT_STREAM_NAME)
    assert len(entries) == 1
    env = EventEnvelope.model_validate_json(entries[0][1]["event"])
    assert env.event_type == "PdfPreprocessingCompleted"
    assert env.source == "pdf-preprocessing"
    assert env.payload.job_id == "job-rec"
    assert env.payload.outcome == "text_restored"
    assert env.payload.output_uri == expected_uri
    assert env.payload.detectors["clip_hidden_text"].spans_restored >= 1
    assert env.payload.detectors["clip_hidden_text"].pages_affected == 1
    assert await redis_client.xlen(app_settings.STREAM_NAME) == 0


async def test_clean_pdf_uploads_nothing_and_reports_clean(
    app_settings, redis_client, s3_stub
):
    state, uploads = s3_stub
    state["clip"] = False

    await handler_mod.handle(_payload("job-clean"), correlation_id="job-clean")

    assert uploads == []
    hstate = await redis_client.hgetall("preprocessing:job-clean")
    assert hstate["outcome"] == "clean"
    assert hstate["output_uri"] == ""

    entries = await redis_client.xrange(app_settings.OUTPUT_STREAM_NAME)
    env = EventEnvelope.model_validate_json(entries[0][1]["event"])
    assert env.payload.outcome == "clean"
    assert env.payload.output_uri is None


async def test_redelivery_is_a_noop_and_publishes_nothing_extra(
    app_settings, redis_client, s3_stub
):
    _, uploads = s3_stub

    await handler_mod.handle(_payload("job-idem"), correlation_id="job-idem")
    await handler_mod.handle(_payload("job-idem"), correlation_id="job-idem")

    # work (fetch/restore/upload) runs both times; only one publish
    assert len(uploads) == 2
    assert await redis_client.xlen(app_settings.OUTPUT_STREAM_NAME) == 1


async def test_fetch_failure_propagates_and_writes_no_state(
    app_settings, redis_client, s3_stub, monkeypatch
):
    async def boom(source_uri, dst):
        raise S3Error("NoSuchKey")

    monkeypatch.setattr(handler_mod, "fetch_pdf", boom)

    with pytest.raises(S3Error):
        await handler_mod.handle(_payload("job-fail"), correlation_id="job-fail")

    assert await redis_client.exists("preprocessing:job-fail") == 0
    assert await redis_client.xlen(app_settings.OUTPUT_STREAM_NAME) == 0
