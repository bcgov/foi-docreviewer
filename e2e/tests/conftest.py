from __future__ import annotations

import pytest

import clients
import settings as settings_module


@pytest.fixture(scope="session")
def settings() -> settings_module.Settings:
    return settings_module.load()


@pytest.fixture(scope="session")
def pg(settings) -> clients.Postgres:
    return clients.Postgres(settings.db_dsn)


@pytest.fixture(scope="session")
def redis_client(settings) -> clients.Redis:
    return clients.Redis(settings.redis_url)


@pytest.fixture(scope="session")
def s3(settings) -> clients.S3:
    client = clients.S3(settings)
    client.ensure_bucket()
    return client


@pytest.fixture(scope="session")
def activemq(settings) -> clients.ActiveMQ:
    return clients.ActiveMQ(settings)


@pytest.fixture(scope="session")
def samples_dir(settings) -> str:
    return settings.samples_dir


@pytest.fixture(scope="session", autouse=True)
def stack_ready(redis_client, settings) -> None:
    """Block every test until File Conversion, Dedupe and OCR have their
    consumer groups on their streams, so a pipeline test's XADD is never
    delivered to a group that hasn't been created at `$` yet."""
    expected = [
        (settings.conversion_stream, settings.conversion_group),
        (settings.dedupe_stream, settings.dedupe_group),
        (settings.ocr_stream, settings.ocr_group),
    ]
    for stream, group in expected:
        def check(stream=stream, group=group) -> bool:
            return redis_client.has_group(stream, group)

        def describe(stream=stream, group=group) -> str:
            return f"group {group!r} not yet on stream {stream!r}"

        clients.wait_until(check, timeout=settings.stage_timeout, describe=describe)
