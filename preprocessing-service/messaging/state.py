# messaging/state.py
"""
The handler-side Redis client.

Deliberately separate from the consumer's client. A handler has no ambient
request context — there is no Depends(get_db) equivalent — so it acquires its
own resources, and it must not reach into the consumer's connection to do it.
Keeping them apart means a handler cannot accidentally issue a blocking
command on the connection the read loop depends on.
"""

from redis.asyncio import Redis

from config.logging import get_logger
from config.settings import get_settings

logger = get_logger(__name__)

_client: Redis | None = None


def get_state_client() -> Redis:
    """
    Process-wide state client. Lazily constructed so importing this module
    does not open a socket.
    """
    global _client
    if _client is None:
        _client = Redis.from_url(get_settings().REDIS_STREAM_URL, decode_responses=True)
    return _client


async def close_state_client() -> None:
    """Dispose of the process-wide state client. Called on worker shutdown."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
        logger.debug("Redis state client closed")
