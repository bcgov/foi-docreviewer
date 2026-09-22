"""Fails fast with a clear message when the stack itself is not ready."""
from __future__ import annotations

import glob
import os

from conftest import REQUIRED_TABLES


def test_database_has_ocr_tables(pg):
    rows = pg.all("select table_name from information_schema.tables where table_schema = 'public'")
    missing = REQUIRED_TABLES - {row[0] for row in rows}
    assert not missing, f"missing tables: {sorted(missing)}"


def test_s3_bucket_exists(s3):
    s3.put_bytes("readiness/ping.txt", b"ping", "text/plain")
    assert s3.exists("readiness/ping.txt")


def test_activemq_rest_is_reachable(activemq):
    assert activemq.reachable()


def test_mock_azure_is_healthy(mock_azure):
    assert mock_azure.healthy()
    assert mock_azure.stats()["analyze"] == 0


def test_status_api_rejects_missing_secret(status_api):
    assert status_api.reachable()


def test_worker_has_completed_a_run(settings):
    files = glob.glob(os.path.join(settings.worker_log_dir, "*dococrlog.txt"))
    assert files, "worker never wrote a daily log file"
    text = open(files[0], encoding="utf-8", errors="replace").read()
    assert "RUN_SUMMARY " in text, "worker has not completed a run yet"


def test_samples_are_mounted(samples_dir):
    assert os.path.isfile(os.path.join(samples_dir, "sample.pdf"))
