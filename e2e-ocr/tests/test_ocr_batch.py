"""Several messages in one run: all complete, concurrency stays within the configured bound."""
from __future__ import annotations

import os

import clients
import seed
import stages

FILENAME = "sample.pdf"


def _publish_batch(pg, s3, activemq, samples_dir, prefix: int, count: int) -> list[tuple[seed.Ids, str, bytes]]:
    docs = []
    for n in range(count):
        ids = seed.new_ids(prefix=prefix, n=n)
        data = seed.unique_pdf(os.path.join(samples_dir, FILENAME), str(ids.documentid))
        key = f"requests/{ids.requestnumber}/{n}-{FILENAME}"
        s3.put_bytes(key, data)
        seed.seed_document(pg, ids, s3.url(key), FILENAME, len(data))
        docs.append((ids, key, data))
    for ids, key, _ in docs:
        activemq.publish(seed.queue_message(ids, s3.url(key)))
    return docs


def test_batch_of_10_all_complete(pg, s3, activemq, mock_azure, settings, samples_dir):
    mock_azure.scenario(submit_latency_ms=500)
    docs = _publish_batch(pg, s3, activemq, samples_dir, prefix=3, count=10)

    for ids, key, data in docs:
        outcome = stages.wait_for_ocr_done(pg, settings, ids)
        assert outcome.ocrfilepath == s3.url(stages.ocr_key_for(key))
        assert s3.get(stages.ocr_key_for(key)) == data

    stats = stages.wait_for_mock_idle(mock_azure, settings)
    assert stats["analyze"] == 10
    assert stats["max_concurrent_analyze"] <= settings.max_concurrent
    assert all(op["pdf_fetched"] for op in stats["ops"].values())


def test_ocrjobrunning_posted_once_per_document(pg, s3, activemq, mock_azure, settings, samples_dir):
    mock_azure.scenario(processing_polls=4)
    (ids, key, data), = _publish_batch(pg, s3, activemq, samples_dir, prefix=4, count=1)

    outcome = stages.wait_for_ocr_done(pg, settings, ids)
    assert outcome.chain.count("ocrjobrunning") == 1, outcome.chain


def test_streaming_dequeue_leaves_unstarted_messages_on_broker(pg, s3, activemq, mock_azure, settings, samples_dir):
    """Workers pull one message each only when free: while a batch is in flight the
    broker must still hold the rest, so a hard kill can lose at most max_concurrent."""
    mock_azure.scenario(submit_latency_ms=4000)
    count = 3 * settings.max_concurrent
    docs = _publish_batch(pg, s3, activemq, samples_dir, prefix=11, count=count)

    def some_in_flight() -> bool:
        return mock_azure.stats()["analyze"] >= 1

    clients.wait_until(some_in_flight, timeout=settings.stage_timeout, describe=lambda: "no Analyze call started")
    remaining = activemq.queue_size()
    assert remaining >= count - settings.max_concurrent, (
        f"{count - remaining} messages taken from the broker while only {settings.max_concurrent} can be in flight"
    )

    for ids, key, data in docs:
        stages.wait_for_ocr_done(pg, settings, ids)
    assert activemq.queue_size() == 0
