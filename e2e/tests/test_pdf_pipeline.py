"""A dedupe-ready PDF: upload -> Dedupe -> Compression -> OCRServices -> ActiveMQ."""
from __future__ import annotations

import os

import seed
import stages

FILENAME = "sample.pdf"


def test_pdf_flows_through_dedupe_compression_and_ocr_dispatch(pg, redis_client, s3, activemq, settings, samples_dir):
    ids = seed.new_ids(prefix=1)
    sample = os.path.join(samples_dir, FILENAME)
    key = f"requests/{ids.requestnumber}/{FILENAME}"
    s3url = s3.url(key)
    filesize = os.path.getsize(sample)

    s3.put(key, sample, "application/pdf")
    seed.ensure_path_mapper(pg, settings.s3_bucket)
    seed.seed_pdf_upload(pg, ids, s3url, FILENAME, filesize)
    redis_client.xadd(settings.dedupe_stream, seed.upload_message(ids, s3url, FILENAME, filesize, ".pdf"))

    dedupe = stages.wait_for_dedupe(pg, redis_client, settings, ids)
    assert len(dedupe.rank1hash) == 40, "expected a sha1 hex digest"

    compression = stages.wait_for_compression(pg, s3, settings, ids, dedupe.compressionjobid)
    assert compression.status in ("completed", "skipped")

    payload = stages.wait_for_ocr_dispatch(pg, redis_client, activemq, settings, ids, dedupe.compressionjobid)
    expected_path = compression.compressedfilepath or s3url
    assert expected_path in (payload.get("compresseds3filepath"), payload.get("s3filepath"))
