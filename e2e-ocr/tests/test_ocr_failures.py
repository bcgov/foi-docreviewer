"""A failing document must be reported as failed and must not affect its neighbours."""
from __future__ import annotations

import os

import seed
import stages

FILENAME = "sample.pdf"


def _prepare(pg, s3, samples_dir, prefix: int, n: int, upload: bool = True):
    ids = seed.new_ids(prefix=prefix, n=n)
    data = seed.unique_pdf(os.path.join(samples_dir, FILENAME), str(ids.documentid))
    key = f"requests/{ids.requestnumber}/{n}-{FILENAME}"
    if upload:
        s3.put_bytes(key, data)
    seed.seed_document(pg, ids, s3.url(key), FILENAME, len(data))
    return ids, key, data


def test_azure_failed_status_marks_job_failed(pg, s3, activemq, mock_azure, settings, samples_dir):
    bad = _prepare(pg, s3, samples_dir, prefix=9, n=0)
    good = _prepare(pg, s3, samples_dir, prefix=9, n=1)
    mock_azure.scenario(fail_ops_matching=[seed.sha1(bad[2])])
    for ids, key, _ in (bad, good):
        activemq.publish(seed.queue_message(ids, s3.url(key)))

    bad_chain = stages.wait_for_status(pg, settings, bad[0], "ocrjobfailed")
    assert bad_chain[-1] == "ocrjobfailed"
    assert "ocrjobsucceeded" not in bad_chain

    good_outcome = stages.wait_for_ocr_done(pg, settings, good[0])
    assert good_outcome.chain[-1] == "ocrjobsucceeded"

    assert not s3.exists(stages.ocr_key_for(bad[1]))
    (bad_path,) = pg.one('SELECT ocrfilepath FROM "DocumentMaster" WHERE documentmasterid = %s', (bad[0].documentmasterid,))
    assert bad_path is None


def test_missing_source_object_does_not_block_batch(pg, s3, activemq, mock_azure, settings, samples_dir):
    missing = _prepare(pg, s3, samples_dir, prefix=10, n=0, upload=False)
    good_a = _prepare(pg, s3, samples_dir, prefix=10, n=1)
    good_b = _prepare(pg, s3, samples_dir, prefix=10, n=2)
    for ids, key, _ in (missing, good_a, good_b):
        activemq.publish(seed.queue_message(ids, s3.url(key)))

    for ids, key, data in (good_a, good_b):
        stages.wait_for_ocr_done(pg, settings, ids)
        assert s3.get(stages.ocr_key_for(key)) == data

    chain = stages.wait_for_status(pg, settings, missing[0], "ocrjobfailed")
    assert chain[-1] == "ocrjobfailed"
