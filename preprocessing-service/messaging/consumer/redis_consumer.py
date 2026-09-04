# messaging/consumer/redis_consumer.py

import asyncio
import traceback
from datetime import UTC, datetime
from uuid import uuid4

from opentelemetry import trace
from opentelemetry.propagate import extract
from pydantic import ValidationError
from redis.asyncio import Redis
from redis.exceptions import RedisError, ResponseError

from config.logging import get_logger
from config.settings import get_settings
from messaging.consumer.dispatcher import dispatch_event
from messaging.models import EventEnvelope

logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)


class RedisConsumer:
    """
    Redis Streams consumer.

    Guarantees:
    - A message is acked only after it has been handled or parked in the DLQ,
      so nothing is silently dropped.
    - Handler failures are retried, then dead-lettered.
    - Messages orphaned by a crash are reclaimed with XAUTOCLAIM.
    """

    def __init__(self, consumer_name: str | None = None) -> None:
        settings = get_settings()

        # Async client: a sync client here would block the event loop that is
        # also serving HTTP.
        self.redis = Redis.from_url(settings.REDIS_STREAM_URL, decode_responses=True)

        self.stream_name = settings.STREAM_NAME
        self.consumer_group = settings.CONSUMER_GROUP
        self.dlq_stream = settings.dlq_stream
        self.consumer_name = consumer_name or f"consumer-{uuid4().hex[:8]}"

        self.block_ms = settings.STREAM_POLL_INTERVAL_MS
        self.batch_size = settings.CONSUMER_BATCH_SIZE
        self.max_retries = settings.CONSUMER_MAX_RETRIES
        self.retry_backoff_ms = settings.CONSUMER_RETRY_BACKOFF_MS
        self.claim_min_idle_ms = settings.CONSUMER_CLAIM_MIN_IDLE_MS

        self.running = False

    # ------------------------------------------------------------------
    # Consumer group
    # ------------------------------------------------------------------

    async def ensure_group(self) -> None:
        """
        Create the consumer group if absent.

        Deliberately NOT in __init__: constructing a consumer must not open a
        socket, or the class is untestable and startup dies whenever Redis
        blinks.
        """
        try:
            await self.redis.xgroup_create(
                name=self.stream_name,
                groupname=self.consumer_group,
                id="0",
                mkstream=True,
            )
            logger.info(
                "Consumer group created",
                stream=self.stream_name,
                group=self.consumer_group,
            )
        except ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise
            logger.info(
                "Consumer group already exists",
                stream=self.stream_name,
                group=self.consumer_group,
            )

    # ------------------------------------------------------------------
    # Dead letter
    # ------------------------------------------------------------------

    async def _dead_letter(
        self,
        message_id: str,
        fields: dict,
        reason: str,
        error: str,
        delivery_count: int = 0,
    ) -> None:
        """Park a message in the DLQ, then ack the original."""
        await self.redis.xadd(
            name=self.dlq_stream,
            fields={
                "event": fields.get("event", ""),
                "original_message_id": message_id,
                "original_stream": self.stream_name,
                "reason": reason,
                "error": error[:4000],
                "delivery_count": str(delivery_count),
                "failed_at": datetime.now(UTC).isoformat(),
            },
        )
        await self.redis.xack(self.stream_name, self.consumer_group, message_id)
        logger.error(
            "Message dead-lettered",
            message_id=message_id,
            reason=reason,
            dlq=self.dlq_stream,
        )

    # ------------------------------------------------------------------
    # Message processing
    # ------------------------------------------------------------------

    async def _handle_one(self, message_id: str, fields: dict) -> None:
        """
        Process one message: validate, dispatch with retries, ack.

        The ack happens only on success or after dead-lettering, so a message
        never leaves the pending list unaccounted for.
        """
        raw_event = fields.get("event")
        if not raw_event:
            await self._dead_letter(
                message_id, fields, "missing_field", "message has no 'event' field"
            )
            return

        try:
            envelope = EventEnvelope.model_validate_json(raw_event)
        except ValidationError as e:
            # No retries: a message that cannot parse will never parse.
            await self._dead_letter(message_id, fields, "validation_error", str(e))
            return

        carrier = {"traceparent": envelope.traceparent} if envelope.traceparent else {}
        parent_context = extract(carrier)

        # start_as_current_span, NOT a detached span. The producer reads
        # ambient context, so making this span current is the entire mechanism
        # by which an event published from inside a handler continues this
        # trace. A detached span logs and exports identically and silently
        # orphans every downstream hop — which is why test_tracing.py asserts
        # on parent span ids rather than on spans merely existing.
        with tracer.start_as_current_span(
            f"consume {envelope.event_type}", context=parent_context
        ):
            log = logger.bind(
                message_id=message_id,
                event_id=str(envelope.event_id),
                event_type=envelope.event_type,
                correlation_id=envelope.correlation_id,
            )

            last_error = ""
            for attempt in range(1, self.max_retries + 1):
                try:
                    await dispatch_event(envelope)
                    await self.redis.xack(
                        self.stream_name, self.consumer_group, message_id
                    )
                    log.debug("Message handled and acked", attempt=attempt)
                    return
                except Exception as e:
                    last_error = f"{e}\n{traceback.format_exc()}"
                    log.warning(
                        "Handler failed",
                        attempt=attempt,
                        max_retries=self.max_retries,
                        error=str(e),
                    )
                    if attempt < self.max_retries:
                        backoff = self.retry_backoff_ms * (2 ** (attempt - 1)) / 1000
                        await asyncio.sleep(backoff)

            await self._dead_letter(
                message_id, fields, "handler_error", last_error, self.max_retries
            )

    # ------------------------------------------------------------------
    # Crash recovery
    # ------------------------------------------------------------------

    async def reclaim_orphans(self) -> None:
        """
        Pick up messages left pending by a process that died mid-handler.

        A reclaimed message whose delivery count already exceeds the limit is
        dead-lettered immediately: otherwise a message that crashes the process
        is reclaimed and re-crashes it forever.
        """
        try:
            claim_result = await self.redis.xautoclaim(
                name=self.stream_name,
                groupname=self.consumer_group,
                consumername=self.consumer_name,
                min_idle_time=self.claim_min_idle_ms,
                count=self.batch_size,
            )
            # Redis 7.0+ adds a third element listing message ids
            # deleted from the stream - this handles all versions
            messages = claim_result[1]
        except ResponseError as e:
            logger.warning("XAUTOCLAIM failed", error=str(e))
            return

        for message_id, fields in messages:
            pending = await self.redis.xpending_range(
                self.stream_name,
                self.consumer_group,
                min=message_id,
                max=message_id,
                count=1,
            )
            delivery_count = pending[0]["times_delivered"] if pending else 1

            if delivery_count > self.max_retries:
                await self._dead_letter(
                    message_id,
                    fields,
                    "poison_message",
                    f"delivered {delivery_count} times without success",
                    delivery_count,
                )
                continue

            logger.info("Reclaimed orphaned message", message_id=message_id)
            await self._handle_one(message_id, fields)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Run until stop() is called. Finishes the current message first."""
        await self.ensure_group()
        await self.reclaim_orphans()

        self.running = True
        logger.info(
            "Consumer started",
            stream=self.stream_name,
            group=self.consumer_group,
            consumer=self.consumer_name,
        )

        while self.running:
            try:
                response = await self.redis.xreadgroup(
                    groupname=self.consumer_group,
                    consumername=self.consumer_name,
                    streams={self.stream_name: ">"},
                    count=self.batch_size,
                    block=self.block_ms,
                )
            except ResponseError as e:
                logger.error("XREADGROUP failed", error=str(e))
                await asyncio.sleep(self.block_ms / 1000)
                continue
            except RedisError as e:
                # Connection drops, Redis restarts, etc: never let this
                # escape the loop, or the consumer dies silently with a
                # still-healthy-looking /health.
                logger.error("Redis error in consumer loop", error=str(e))
                await asyncio.sleep(self.block_ms / 1000)
                continue

            if not response:
                await self.reclaim_orphans()
                continue

            for _stream, messages in response:
                for message_id, fields in messages:
                    if not self.running:
                        break
                    await self._handle_one(message_id, fields)

        logger.info("Consumer loop exited", consumer=self.consumer_name)

    async def stop(self) -> None:
        """Signal the loop to finish its current message and return."""
        self.running = False

    async def close(self) -> None:
        await self.redis.aclose()
        logger.debug("Redis consumer connection closed")
