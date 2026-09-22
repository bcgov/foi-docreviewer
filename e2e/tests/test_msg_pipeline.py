"""A conversion-required Outlook MSG: upload -> File Conversion -> Dedupe -> Compression -> OCR dispatch.

The sample is a synthetic email (MsgKit-generated, no real content) carrying
14 generic .msg attachments plus two inline body images. Inline images are
rendered into the PDF; each .msg attachment becomes its own DocumentMaster row
under `parentid` and is re-queued for conversion.
"""
from __future__ import annotations

import os

import seed
import stages

FILENAME = "msg-with-attachments.msg"
MSG_TYPE = "application/vnd.ms-outlook"
ATTACHMENT_COUNT = 14


def _dedupe_jobid_for(redis_client, settings, ids) -> int:
    for _, fields in redis_client.entries(settings.dedupe_stream):
        if fields.get("documentmasterid") == str(ids.documentmasterid):
            return int(fields["jobid"])
    raise AssertionError("dedupe message disappeared between stages")


def test_msg_flows_through_conversion_dedupe_compression_and_ocr_dispatch(pg, redis_client, s3, activemq, settings, samples_dir):
    ids = seed.new_ids(prefix=5)
    sample = os.path.join(samples_dir, FILENAME)
    key = f"requests/{ids.requestnumber}/{FILENAME}"
    s3url = s3.url(key)
    filesize = os.path.getsize(sample)

    s3.put(key, sample, MSG_TYPE)
    seed.ensure_path_mapper(pg, settings.s3_bucket)
    seed.seed_conversion_upload(pg, ids, s3url, FILENAME, filesize, ".msg")
    redis_client.xadd(settings.conversion_stream, seed.upload_message(ids, s3url, FILENAME, filesize, ".msg"))

    conversion = stages.wait_for_conversion(pg, s3, redis_client, settings, ids)
    assert conversion.pdf_url == s3url[: -len(".msg")] + ".pdf"

    attachments = stages.wait_for_attachment_conversions(pg, settings, ids, expected=ATTACHMENT_COUNT)
    assert all(path.lower().endswith(".msg") for _, path in attachments), attachments
    assert all(f"/{ids.requestnumber}/msg-with-attachments/{ids.jobid}-" in path for _, path in attachments), attachments

    dedupe_jobid = _dedupe_jobid_for(redis_client, settings, ids)
    dedupe = stages.wait_for_dedupe(pg, redis_client, settings, ids, jobid=dedupe_jobid, documentmasterid=conversion.outputdocumentmasterid)
    assert len(dedupe.rank1hash) == 40

    compression = stages.wait_for_compression(pg, s3, settings, ids, dedupe.compressionjobid)
    assert compression.status in ("completed", "skipped")

    payload = stages.wait_for_ocr_dispatch(pg, redis_client, activemq, settings, ids, dedupe.compressionjobid)
    assert payload["documentmasterid"] == ids.documentmasterid
    expected_path = compression.compressedfilepath or conversion.pdf_url
    assert expected_path in (payload.get("compresseds3filepath"), payload.get("s3filepath"))
