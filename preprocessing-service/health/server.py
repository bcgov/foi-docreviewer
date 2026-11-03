# health/server.py
"""
A probe endpoint, not a web framework.

The worker has no HTTP surface, but an orchestrator still needs to ask whether
it is alive and whether it can reach Redis. That is roughly forty lines of
asyncio, so it does not justify a dependency on an ASGI server. Everything
here is deliberately unambitious: one route, no keep-alive, no routing table,
no request body parsing.
"""

import asyncio
import json

from redis.asyncio import Redis

from config.logging import get_logger
from config.settings import get_settings

logger = get_logger(__name__)

PROBE_TIMEOUT_SECONDS = 2.0
REQUEST_LINE_TIMEOUT_SECONDS = 5.0


async def _redis_is_reachable() -> bool:
    client = Redis.from_url(get_settings().REDIS_STREAM_URL, decode_responses=True)
    try:
        await asyncio.wait_for(client.ping(), timeout=PROBE_TIMEOUT_SECONDS)
        return True
    except Exception as e:
        logger.warning("Health probe failed", dependency="redis", error=str(e))
        return False
    finally:
        await client.aclose()


def _response(status_line: bytes, payload: dict) -> bytes:
    body = json.dumps(payload).encode()
    return (
        b"HTTP/1.1 " + status_line + b"\r\n"
        b"Content-Type: application/json\r\n"
        b"Content-Length: " + str(len(body)).encode() + b"\r\n"
        b"Connection: close\r\n"
        b"\r\n" + body
    )


async def _handle_client(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter
) -> None:
    try:
        line = await asyncio.wait_for(
            reader.readline(), timeout=REQUEST_LINE_TIMEOUT_SECONDS
        )
        parts = line.decode("latin-1").split()
        path = parts[1].split("?")[0] if len(parts) > 1 else "/"

        if path != "/health":
            writer.write(_response(b"404 Not Found", {"error": "not found"}))
        elif await _redis_is_reachable():
            writer.write(_response(b"200 OK", {"status": "ok", "redis": "ok"}))
        else:
            writer.write(
                _response(
                    b"503 Service Unavailable",
                    {"status": "degraded", "redis": "down"},
                )
            )
        await writer.drain()
    except Exception as e:
        # A failing probe connection must never take down the worker.
        logger.warning("Health request failed", error=str(e))
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass


async def start_health_server(port: int | None = None) -> asyncio.Server:
    """
    Bind and start serving in the background.

    Returns the server so the caller owns its lifetime. Pass port=0 in tests to
    get an ephemeral port from the OS instead of fighting over a fixed one.
    """
    bind_port = get_settings().HEALTH_PORT if port is None else port
    server = await asyncio.start_server(_handle_client, "0.0.0.0", bind_port)
    logger.info("Health server listening", port=server.sockets[0].getsockname()[1])
    return server
