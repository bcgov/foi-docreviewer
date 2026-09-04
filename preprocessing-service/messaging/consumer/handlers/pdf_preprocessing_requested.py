from datetime import UTC, datetime
from pathlib import Path

from config.logging import get_logger
from config.settings import get_settings
from core.pipeline import run_pipeline
from core.s3 import fetch_pdf, suffix_uri, upload_pdf
from messaging.models import (
    DetectorOutcome,
    EventEnvelope,
    PdfPreprocessingCompletedEvent,
    PdfPreprocessingRequestedEvent,
)
from messaging.producer.redis_producer import get_producer
from messaging.state import get_state_client

logger = get_logger(__name__)


async def handle(
    payload: PdfPreprocessingRequestedEvent, *, correlation_id: str
) -> None:
    """
    Consume -> fetch -> restore -> upload -> publish. The shape every handler in
    this template takes.

    THE PROCESSING STEP: read the source object from S3, run the registered
    detectors to find and restore hidden text, upload the restored PDF beside the
    source (`<name>.pdf` -> `<name><OUTPUT_FILENAME_SUFFIX>.pdf`, same bucket and
    prefix), and publish PdfPreprocessingCompleted to OUTPUT_STREAM_NAME for the
    next service. Replace the fetch + `restore_pdf` + upload with whatever your
    service actually does.

    IDEMPOTENCY: Redis Streams delivers at least once. HSETNX on
    `preprocessing:<job_id>` is the guard -- exactly one delivery per job_id
    takes the publish path; a redelivery sees 0, logs, and returns BEFORE the
    publish, so a duplicate inbound event never becomes a duplicate
    PdfPreprocessingCompleted downstream.

    ORDER, on purpose: the fetch, restoration and upload run BEFORE the guard is
    set, so a transient failure (throttling, timeout) raises, the consumer
    retries, and the retry re-runs the work instead of short-circuiting on the
    guard. The output key is derived from the source URI, so a re-run overwrites
    it. Two consumers racing the same redelivery may both do the (wasted) work,
    but HSETNX lets only one publish.

    FAILURE WINDOW, documented not solved: if the work succeeds, HSETNX
    succeeds, then the publish below fails, this raises and is retried -- but
    the retry finds HSETNX returning 0 and takes the early return, so
    PdfPreprocessingCompleted is never published. The restored object is in S3
    and the downstream event is lost. That is the write-then-publish problem;
    the real fix is a transactional outbox.

    RESOURCES: the handler takes its own Redis client (messaging/state.py), not
    the consumer's; the S3 client is process-wide (core/s3.py).
    """
    settings = get_settings()
    job_id = payload.job_id
    log = logger.bind(job_id=job_id, correlation_id=correlation_id)

    work = Path(settings.WORK_DIR)
    src_path = work / f"{job_id}.src.pdf"
    out_path = work / f"{job_id}.out.pdf"
    # Restored PDF goes back beside the source: <name>.pdf -> <name>PREPROCESSED.pdf
    output_uri = suffix_uri(payload.source_uri, settings.OUTPUT_FILENAME_SUFFIX)

    try:
        await fetch_pdf(payload.source_uri, src_path)
        result = run_pipeline(src_path, out_path)
        if result.wrote_output:
            await upload_pdf(out_path, output_uri)
    finally:
        src_path.unlink(missing_ok=True)
        out_path.unlink(missing_ok=True)

    outcome = "text_restored" if result.hidden_found else "clean"

    redis = get_state_client()
    key = f"preprocessing:{job_id}"
    if not await redis.hsetnx(key, "outcome", outcome):
        log.info("Job already processed; nothing to do")
        return

    completed_at = datetime.now(UTC)
    detectors = {
        name: DetectorOutcome(
            spans_restored=detector_result.spans_restored,
            pages_affected=detector_result.pages_affected,
        )
        for name, detector_result in result.detectors.items()
        if detector_result.spans_restored
    }
    await redis.hset(
        key,
        mapping={
            "spans_restored": result.spans_restored,
            "pages_affected": result.pages_affected,
            "output_uri": output_uri if result.wrote_output else "",
            "completed_at": completed_at.isoformat(),
        },
    )
    await redis.expire(key, settings.STATE_TTL_SECONDS)

    # Publishing from inside a handler is what makes this a pipeline node. The
    # producer reads ambient trace context, so this event is automatically a
    # child of the span for the message being handled.
    await get_producer().publish(
        EventEnvelope.create(
            event_type="PdfPreprocessingCompleted",
            payload=PdfPreprocessingCompletedEvent(
                job_id=job_id,
                outcome=outcome,
                spans_restored=result.spans_restored,
                pages_affected=result.pages_affected,
                detectors=detectors,
                output_uri=output_uri if result.wrote_output else None,
                completed_at=completed_at,
            ),
            correlation_id=correlation_id,
            source="pdf-preprocessing",
        ),
        stream=settings.OUTPUT_STREAM_NAME,
    )

    log.info(
        "Preprocessing complete",
        outcome=outcome,
        spans_restored=result.spans_restored,
        pages_affected=result.pages_affected,
    )
