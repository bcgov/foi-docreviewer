"""A conversion-required DOCX: upload -> File Conversion -> Dedupe -> Compression -> OCR dispatch."""
from __future__ import annotations

import os

import seed
import stages

FILENAME = "simple-test-doc.docx"
DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _dedupe_jobid_for(redis_client, settings, ids) -> int:
    for _, fields in redis_client.entries(settings.dedupe_stream):
        if fields.get("documentmasterid") == str(ids.documentmasterid):
            return int(fields["jobid"])
    raise AssertionError("dedupe message disappeared between stages")


def test_docx_flows_through_conversion_dedupe_compression_and_ocr_dispatch(pg, redis_client, s3, activemq, settings, samples_dir):
    ids = seed.new_ids(prefix=2)
    sample = os.path.join(samples_dir, FILENAME)
    key = f"requests/{ids.requestnumber}/{FILENAME}"
    s3url = s3.url(key)
    filesize = os.path.getsize(sample)

    s3.put(key, sample, DOCX_TYPE)
    seed.ensure_path_mapper(pg, settings.s3_bucket)
    seed.seed_docx_upload(pg, ids, s3url, FILENAME, filesize)
    redis_client.xadd(settings.conversion_stream, seed.upload_message(ids, s3url, FILENAME, filesize, ".docx"))

    conversion = stages.wait_for_conversion(pg, s3, redis_client, settings, ids)
    assert conversion.pdf_url == s3url[: -len(".docx")] + ".pdf"

    dedupe_jobid = _dedupe_jobid_for(redis_client, settings, ids)
    dedupe = stages.wait_for_dedupe(pg, redis_client, settings, ids, jobid=dedupe_jobid)
    assert len(dedupe.rank1hash) == 40

    compression = stages.wait_for_compression(pg, s3, settings, ids, dedupe.compressionjobid)
    assert compression.status in ("completed", "skipped")

    payload = stages.wait_for_ocr_dispatch(pg, redis_client, activemq, settings, ids, dedupe.compressionjobid)
    assert payload["documentmasterid"] == ids.documentmasterid
