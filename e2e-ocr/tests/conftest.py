from __future__ import annotations

import glob
import os
import shutil

import pytest

import clients
import settings as settings_module

REQUIRED_TABLES = {"DocumentOCRJob", "DocumentMaster", "Documents", "DocumentAttributes"}


@pytest.fixture(scope="session")
def settings() -> settings_module.Settings:
    return settings_module.load()


@pytest.fixture(scope="session")
def pg(settings) -> clients.Postgres:
    return clients.Postgres(settings.db_dsn)


@pytest.fixture(scope="session")
def s3(settings) -> clients.S3:
    client = clients.S3(settings)
    client.ensure_bucket()
    return client


@pytest.fixture(scope="session")
def activemq(settings) -> clients.ActiveMQ:
    return clients.ActiveMQ(settings)


@pytest.fixture(scope="session")
def mock_azure(settings) -> clients.MockAzure:
    return clients.MockAzure(settings)


@pytest.fixture(scope="session")
def status_api(settings) -> clients.StatusApi:
    return clients.StatusApi(settings)


@pytest.fixture(scope="session")
def samples_dir(settings) -> str:
    return settings.samples_dir


@pytest.fixture(scope="session", autouse=True)
def stack_ready(settings, pg, s3, activemq, mock_azure, status_api) -> None:
    """Block every test until each component answers and the worker has completed a run."""
    def tables_present() -> bool:
        rows = pg.all("select table_name from information_schema.tables where table_schema = 'public'")
        return REQUIRED_TABLES <= {row[0] for row in rows}

    def worker_has_logged() -> bool:
        return bool(glob.glob(os.path.join(settings.worker_log_dir, "*dococrlog.txt")))

    checks = [
        ("postgres tables", tables_present),
        ("activemq rest", activemq.reachable),
        ("mock azure", mock_azure.healthy),
        ("status api", status_api.reachable),
        ("worker log file", worker_has_logged),
    ]
    for label, check in checks:
        clients.wait_until(check, timeout=settings.stage_timeout, describe=lambda label=label: f"{label} not ready")


@pytest.fixture(autouse=True)
def fresh_mock(mock_azure) -> None:
    """Every test starts from the default scenario with empty stats."""
    mock_azure.reset()


def pytest_sessionfinish(session, exitstatus):
    """Copy the worker's daily log files next to junit.xml for post-mortems."""
    src = os.environ.get("E2E_OCR_WORKER_LOG_DIR", "/var/log/ocr")
    dst = "/test-results"
    if os.path.isdir(src) and os.path.isdir(dst):
        for path in glob.glob(os.path.join(src, "*dococrlog.txt")):
            shutil.copy(path, os.path.join(dst, "worker-" + os.path.basename(path)))
