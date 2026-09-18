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
