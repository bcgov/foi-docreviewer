"""Azure 429s on submit, poll and result; concurrency cap. Strict xfails document today's behaviour."""
from __future__ import annotations

import os

import pytest

import seed
import stages

FILENAME = "sample.pdf"


def _publish_one(pg, s3, activemq, samples_dir, prefix: int, n: int = 0):
    ids = seed.new_ids(prefix=prefix, n=n)
    data = seed.unique_pdf(os.path.join(samples_dir, FILENAME), str(ids.documentid))
    key = f"requests/{ids.requestnumber}/{n}-{FILENAME}"
    s3.put_bytes(key, data)
    seed.seed_document(pg, ids, s3.url(key), FILENAME, len(data))
    activemq.publish(seed.queue_message(ids, s3.url(key)))
    return ids, key, data


@pytest.mark.xfail(
    strict=True,
    reason="findings §3: 429 on Analyze POST is 'unexpected status code', no retry, no status posted",
)
def test_submit_429_is_retried(pg, s3, activemq, mock_azure, settings, samples_dir):
    mock_azure.scenario(submit_429_first=2, retry_after_seconds=1)
    ids, key, data = _publish_one(pg, s3, activemq, samples_dir, prefix=5)

    outcome = stages.wait_for_ocr_done(pg, settings, ids)
    assert "ocrjobfailed" not in outcome.chain

    stats = stages.wait_for_mock_idle(mock_azure, settings)
    assert stats["analyze"] == 3
    assert stats["http429"]["submit"] == 2
    gaps = [b - a for a, b in zip(stats["analyze_timestamps"], stats["analyze_timestamps"][1:])]
    assert all(gap >= 1.0 for gap in gaps), f"Retry-After not honoured: gaps={gaps}"


@pytest.mark.xfail(
    strict=True,
    reason="findings §3: a 429 on the status GET has no `status` field, falls to the default branch and posts ocrjobfailed",
)
def test_poll_429_does_not_fail_job(pg, s3, activemq, mock_azure, settings, samples_dir):
    mock_azure.scenario(poll_429_first=2)
    ids, key, data = _publish_one(pg, s3, activemq, samples_dir, prefix=6)

    outcome = stages.wait_for_ocr_done(pg, settings, ids)
    assert "ocrjobfailed" not in outcome.chain
    stats = stages.wait_for_mock_idle(mock_azure, settings)
    assert stats["http429"]["poll"] == 2


@pytest.mark.xfail(
    strict=True,
    reason="findings §3: 429 on the /pdf GET aborts with 'failed to retrieve PDF', DB stays at ocrjobsucceeded with no file",
)
def test_result_429_is_retried(pg, s3, activemq, mock_azure, settings, samples_dir):
    mock_azure.scenario(result_429_first=1)
    ids, key, data = _publish_one(pg, s3, activemq, samples_dir, prefix=7)

    outcome = stages.wait_for_ocr_done(pg, settings, ids)
    assert s3.get(stages.ocr_key_for(key)) == data
    stats = stages.wait_for_mock_idle(mock_azure, settings)
    assert stats["pdf"] == 2


def test_analyze_concurrency_cap_is_respected(pg, s3, activemq, mock_azure, settings, samples_dir):
    """Passes today because the worker is sequential; guards the future worker pool
    (maxconcurrentocrjobs must never exceed what Azure accepts)."""
    mock_azure.scenario(max_concurrent_analyze=2, submit_latency_ms=1000)
    docs = [_publish_one(pg, s3, activemq, samples_dir, prefix=8, n=n) for n in range(6)]

    for ids, key, data in docs:
        stages.wait_for_ocr_done(pg, settings, ids)

    stats = stages.wait_for_mock_idle(mock_azure, settings)
    assert stats["http429"]["submit"] == 0
    assert stats["max_concurrent_analyze"] <= 2
