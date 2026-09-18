"""Publishing the same PDF twice yields two Documents rows with one rank1hash."""
from __future__ import annotations

import os

import seed
import stages

FILENAME = "sample.pdf"


def _run_pdf(pg, redis_client, s3, activemq, settings, samples_dir, prefix: int):
    ids = seed.new_ids(prefix=prefix)
    sample = os.path.join(samples_dir, FILENAME)
    key = f"requests/{ids.requestnumber}/{FILENAME}"
    s3url = s3.url(key)
    filesize = os.path.getsize(sample)
    s3.put(key, sample, "application/pdf")
    seed.ensure_path_mapper(pg, settings.s3_bucket)
    seed.seed_pdf_upload(pg, ids, s3url, FILENAME, filesize)
    redis_client.xadd(settings.dedupe_stream, seed.upload_message(ids, s3url, FILENAME, filesize, ".pdf"))
    dedupe = stages.wait_for_dedupe(pg, redis_client, settings, ids)
    # Drain the rest of the pipeline so this document's ActiveMQ message does
    # not leak into a later test's consume_one().
    stages.wait_for_compression(pg, s3, settings, ids, dedupe.compressionjobid)
    stages.wait_for_ocr_dispatch(pg, redis_client, activemq, settings, ids, dedupe.compressionjobid)
    return dedupe


def test_same_pdf_twice_records_identical_hash(pg, redis_client, s3, activemq, settings, samples_dir):
    first = _run_pdf(pg, redis_client, s3, activemq, settings, samples_dir, prefix=3)
    second = _run_pdf(pg, redis_client, s3, activemq, settings, samples_dir, prefix=4)

    assert first.documentid != second.documentid
    assert first.rank1hash == second.rank1hash
