import asyncio
import json

import pytest

from health.server import start_health_server

pytestmark = pytest.mark.integration


async def request(port: int, path: str = "/health") -> tuple[int, dict]:
    """Minimal HTTP client — the server is minimal, the client can be too."""
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(f"GET {path} HTTP/1.1\r\nHost: localhost\r\n\r\n".encode())
    await writer.drain()
    raw = await reader.read()
    writer.close()
    await writer.wait_closed()

    head, _, body = raw.partition(b"\r\n\r\n")
    status = int(head.split(b"\r\n")[0].split()[1])
    return status, json.loads(body)


async def serve_on_ephemeral_port():
    server = await start_health_server(port=0)
    return server, server.sockets[0].getsockname()[1]


async def test_health_returns_200_when_redis_is_reachable(app_settings):
    server, port = await serve_on_ephemeral_port()
    try:
        status, body = await request(port)
    finally:
        server.close()
        await server.wait_closed()

    assert status == 200
    assert body == {"status": "ok", "redis": "ok"}


async def test_health_returns_503_when_redis_is_unreachable(app_settings, monkeypatch):
    """
    A health endpoint that always returns 200 teaches the wrong reflex: it
    tells your orchestrator the worker is fine while it cannot reach the
    stream it exists to consume.
    """
    from config.settings import get_settings

    monkeypatch.setenv("REDIS_STREAM_URL", "redis://127.0.0.1:1/0")
    get_settings.cache_clear()

    server, port = await serve_on_ephemeral_port()
    try:
        status, body = await request(port)
    finally:
        server.close()
        await server.wait_closed()
        get_settings.cache_clear()

    assert status == 503
    assert body == {"status": "degraded", "redis": "down"}


async def test_unknown_path_returns_404(app_settings):
    server, port = await serve_on_ephemeral_port()
    try:
        status, _ = await request(port, "/info")
    finally:
        server.close()
        await server.wait_closed()

    assert status == 404
