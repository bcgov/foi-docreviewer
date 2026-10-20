# main.py
"""
Worker entry point.

Two coroutines on one event loop: the Redis Streams consumer, and a health
probe server so an orchestrator can ask how it is doing. There is no HTTP API
— this process exists to consume events.
"""

import asyncio
import signal

from config.logging import configure_logging, get_logger
from config.tracing import init_tracing
from core.s3 import close_s3_client
from health.server import start_health_server
from messaging.consumer import RedisConsumer
from messaging.producer.redis_producer import close_producer
from messaging.state import close_state_client

configure_logging()
init_tracing()

logger = get_logger(__name__)

# How long a handler gets to finish its current message once shutdown starts.
# Keep it under your orchestrator's grace period, or SIGKILL wins the race.
SHUTDOWN_TIMEOUT_SECONDS = 10


def _install_signal_handlers(stop: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            # Not available on every platform; Ctrl-C still raises
            # KeyboardInterrupt, which asyncio.run handles.
            pass


async def run_worker(stop: asyncio.Event | None = None) -> None:
    """
    Run until signalled, then shut down without dropping an in-flight message.

    `stop` is injectable so tests can drive shutdown without sending signals.
    """
    stop = stop or asyncio.Event()
    _install_signal_handlers(stop)

    consumer = RedisConsumer()
    consumer_task = asyncio.create_task(consumer.start())
    consumer_task.add_done_callback(
        lambda t: (
            logger.error("Consumer task died", error=str(t.exception()))
            if not t.cancelled() and t.exception()
            else None
        )
    )

    server = await start_health_server()
    logger.info("Worker started")

    # If the consumer dies on its own, stop waiting — a worker whose consumer
    # is dead but whose health server still answers is the worst outcome.
    consumer_task.add_done_callback(lambda _: stop.set())

    await stop.wait()
    logger.info("Shutting down worker")

    await consumer.stop()
    try:
        await asyncio.wait_for(consumer_task, timeout=SHUTDOWN_TIMEOUT_SECONDS)
    except TimeoutError:
        logger.warning("Consumer did not stop in time; cancelling")
        consumer_task.cancel()
        await asyncio.gather(consumer_task, return_exceptions=True)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        # Whatever killed the consumer must not skip the cleanup below —
        # that would be a resource leak.
        logger.error("Consumer task ended with error", error=str(e))

    server.close()
    await server.wait_closed()

    await consumer.close()
    await close_producer()
    await close_state_client()
    close_s3_client()
    logger.info("Worker stopped; connections closed")


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
