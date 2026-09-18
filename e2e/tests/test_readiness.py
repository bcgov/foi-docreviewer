"""Fails fast with a clear message when the stack itself is not ready."""
from __future__ import annotations

import os

from clients import wait_until

REQUIRED_TABLES = {
    "DocumentPathMapper", "DocumentMaster", "DocumentAttributes", "FileConversionJob",
    "DeduplicationJob", "Documents", "DocumentHashCodes", "CompressionJob",
    "PageCalculatorJob", "OCRActiveMQJob",
}


def test_database_has_pipeline_tables(pg):
    rows = pg.all(
        "select table_name from information_schema.tables where table_schema = 'public'"
    )
    present = {row[0] for row in rows}
    missing = REQUIRED_TABLES - present
    assert not missing, f"missing tables: {sorted(missing)}"


def test_redis_is_reachable(redis_client):
    assert redis_client.ping()


def test_s3_bucket_exists(s3, settings):
    s3.put("readiness/ping.txt", os.path.join(os.path.dirname(__file__), "requirements.txt"), "text/plain")
    assert s3.exists("readiness/ping.txt")


def test_activemq_rest_is_reachable(activemq):
    assert activemq.reachable()


def test_samples_are_mounted(samples_dir):
    assert os.path.isfile(os.path.join(samples_dir, "simple-test-doc.docx"))
    assert os.path.isfile(os.path.join(samples_dir, "sample.pdf"))


def test_workers_registered_consumer_groups(redis_client, settings):
    expected = [
        (settings.conversion_stream, settings.conversion_group),
        (settings.dedupe_stream, settings.dedupe_group),
        (settings.ocr_stream, settings.ocr_group),
    ]
    for stream, group in expected:
        wait_until(
            lambda: redis_client.has_group(stream, group),
            timeout=settings.stage_timeout,
            describe=lambda: f"group {group!r} not yet on stream {stream!r}",
        )
