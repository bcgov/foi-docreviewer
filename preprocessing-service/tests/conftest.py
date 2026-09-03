# tests/conftest.py

import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from testcontainers.redis import RedisContainer


@pytest.fixture(scope="session")
def redis_url() -> str:
    """Start a throwaway Redis and yield its URL."""
    with RedisContainer("redis:7") as rc:
        host = rc.get_container_host_ip()
        port = rc.get_exposed_port(6379)
        yield f"redis://{host}:{port}/0"


@pytest.fixture(scope="session")
def app_settings(redis_url: str):
    """
    Point the application's cached settings at the container.

    get_settings() is lru_cached, so the env must be set and the cache cleared
    before anything imports a Redis client.
    """
    from config.settings import get_settings

    os.environ["REDIS_STREAM_URL"] = redis_url
    os.environ["STREAM_NAME"] = "test.pdf.preprocessing.requests"
    os.environ["CONSUMER_GROUP"] = "test_group"
    os.environ["OUTPUT_STREAM_NAME"] = "test.pdf.preprocessing.completed"
    os.environ["OUTPUT_FILENAME_SUFFIX"] = "PREPROCESSED"
    os.environ["CONSUMER_RETRY_BACKOFF_MS"] = "10"
    get_settings.cache_clear()
    yield get_settings()
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def redis_client(app_settings) -> AsyncGenerator:
    """
    Redis client with the streams and any dedup keys cleared before and after.
    Handlers write preprocessing:* hashes, so leaving them behind would make a
    later test's HSETNX return 0 and silently change its meaning.
    """
    from redis.asyncio import Redis

    client = Redis.from_url(app_settings.REDIS_STREAM_URL, decode_responses=True)

    async def _flush():
        await client.delete(
            app_settings.STREAM_NAME,
            app_settings.OUTPUT_STREAM_NAME,
            app_settings.dlq_stream,
        )
        keys = [k async for k in client.scan_iter(match="preprocessing:*")]
        if keys:
            await client.delete(*keys)

    await _flush()
    yield client
    await _flush()
    await client.aclose()
