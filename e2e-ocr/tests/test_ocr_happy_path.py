"""One PDF: ActiveMQ -> worker -> mock Azure -> S3 <name>OCR.pdf -> azuredococrapi -> Postgres."""
from __future__ import annotations

import os

import seed
import stages

FILENAME = "sample.pdf"


def test_single_pdf_completes(pg, s3, activemq, mock_azure, settings, samples_dir):
    ids = seed.new_ids(prefix=1)
    data = seed.unique_pdf(os.path.join(samples_dir, FILENAME), str(ids.documentid))
    key = f"requests/{ids.requestnumber}/{FILENAME}"
    s3.put_bytes(key, data)
    seed.seed_document(pg, ids, s3.url(key), FILENAME, len(data))

    activemq.publish(seed.queue_message(ids, s3.url(key)))

    outcome = stages.wait_for_ocr_done(pg, settings, ids)

    assert outcome.chain[0] == "azureocrrequestcreated"
    assert outcome.chain[-1] == "ocrjobsucceeded"
    assert "ocrjobrunning" in outcome.chain
    assert "ocrjobfailed" not in outcome.chain

    ocr_key = stages.ocr_key_for(key)
    assert outcome.ocrfilepath == s3.url(ocr_key)
    ocr_bytes = s3.get(ocr_key)
    assert ocr_bytes.startswith(b"%PDF")
    assert ocr_bytes == data, "mock returns the submitted bytes; the uploaded object must be this document's"
    assert outcome.ocrfilesize == len(data)

    stats = stages.wait_for_mock_idle(mock_azure, settings)
    assert stats["analyze"] == 1 and stats["pdf"] == 1
    op = stages.op_for_sha1(stats, seed.sha1(data))
    assert op is not None and op["pdf_fetched"] and op["status"] == "succeeded"
    assert op["polls"] == stats["poll"] >= 3  # notStarted + processing_polls(2) running + succeeded


def test_uses_compressed_path_when_present(pg, s3, activemq, mock_azure, settings, samples_dir):
    ids = seed.new_ids(prefix=2)
    original = seed.unique_pdf(os.path.join(samples_dir, FILENAME), f"{ids.documentid}-original")
    compressed = seed.unique_pdf(os.path.join(samples_dir, FILENAME), f"{ids.documentid}-compressed")
    key = f"requests/{ids.requestnumber}/{FILENAME}"
    compressed_key = f"requests/{ids.requestnumber}/sample-compressed.pdf"
    s3.put_bytes(key, original)
    s3.put_bytes(compressed_key, compressed)
    seed.seed_document(pg, ids, s3.url(key), FILENAME, len(original))

    activemq.publish(seed.queue_message(ids, s3.url(key), compressed_s3url=s3.url(compressed_key)))

    outcome = stages.wait_for_ocr_done(pg, settings, ids)
    assert outcome.ocrfilepath == s3.url(stages.ocr_key_for(compressed_key))
    assert s3.get(stages.ocr_key_for(compressed_key)) == compressed
    assert not s3.exists(stages.ocr_key_for(key))

    stats = stages.wait_for_mock_idle(mock_azure, settings)
    assert stages.op_for_sha1(stats, seed.sha1(compressed)) is not None
    assert stages.op_for_sha1(stats, seed.sha1(original)) is None
