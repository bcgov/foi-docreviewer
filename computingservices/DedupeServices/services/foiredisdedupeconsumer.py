"""
Start processing all records in the stream from the beginning (default, so a
fresh consumer group does not skip an existing backlog):
$ python consumer.py consumer1
$ python consumer.py consumer1 --start-from 0
Start processing only new records published after the consumer group is created:
$ python consumer.py consumer1 --start-from $
"""
import json
import logging
import random
import socket
import time
from datetime import datetime, timezone
from enum import Enum

import typer
from redis.exceptions import RedisError, ResponseError

from utils import (
    dedupe_consumer_batch_size,
    dedupe_consumer_block_ms,
    dedupe_consumer_claim_min_idle_ms,
    dedupe_consumer_group,
    dedupe_consumer_max_retries,
    dedupe_consumer_name,
    dedupe_consumer_retry_backoff_ms,
    dedupe_dlq_maxlen,
    dedupe_dlq_stream,
    dedupe_stream_key,
    redisstreamdb,
)
from . import jsonmessageparser
from .dedupedbservice import isbatchcompleted
from .dedupeservice import initialize_compressionproducer, processmessage
from rstreamio.redisstreamwriter import redisstreamwriter
from utils.loggingutils import log_context, log_event

STREAM_KEY = dedupe_stream_key

app = typer.Typer()
logger = logging.getLogger(__name__)
_MISSING = object()
_DLQ_REDACTED_VALUE = "***REDACTED***"
# Credential/token fields that must never be written verbatim to the DLQ.
# Other fields are preserved so a failed message can still be inspected/replayed.
_DLQ_REDACTED_FIELDS = {"usertoken", "user_token"}


class PermanentMessageError(ValueError):
    pass


def parse_incompatible(value=_MISSING) -> bool:
    if value is _MISSING:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.lower()
        if normalized == "true":
            return True
        if normalized == "false":
            return False
    raise PermanentMessageError("incompatible must be a boolean or string 'true'/'false'")


def parse_message(message):
    try:
        if isinstance(message, str):
            message = json.loads(message)
        elif not isinstance(message, dict):
            raise PermanentMessageError("message must be a mapping or JSON string")

        normalized_message = dict(message)
        normalized_message["incompatible"] = parse_incompatible(
            normalized_message["incompatible"] if "incompatible" in normalized_message else _MISSING
        )
        return jsonmessageparser.getdedupeproducermessage(json.dumps(normalized_message))
    except PermanentMessageError:
        raise
    except (TypeError, ValueError) as error:
        raise PermanentMessageError(str(error)) from error


class StartFrom(str, Enum):
    beginning = "0"
    latest = "$"


class RedisDedupeConsumer:
    def __init__(
        self,
        *,
        redis_client,
        stream_name,
        group_name,
        consumer_name,
        batch_size,
        block_ms,
        max_retries,
        retry_backoff_ms,
        claim_min_idle_ms,
        dlq_stream,
        sleep=None,
        jitter=None,
        group_start_id="0",
        dlq_maxlen=dedupe_dlq_maxlen,
    ):
        self.redis = redis_client
        self.stream_name = stream_name
        self.group_name = group_name
        self.consumer_name = consumer_name
        self.batch_size = batch_size
        self.block_ms = block_ms
        self.max_retries = max_retries
        self.retry_backoff_ms = retry_backoff_ms
        self.claim_min_idle_ms = claim_min_idle_ms
        self.dlq_stream = dlq_stream
        self.dlq_maxlen = dlq_maxlen
        self.sleep = sleep or time.sleep
        self.group_start_id = group_start_id
        self.running = False
        self.jitter = jitter or (
            lambda attempt: random.uniform(0, self.retry_backoff_ms / 1000)
        )

    def ensure_group(self):
        try:
            self.redis.xgroup_create(
                name=self.stream_name,
                groupname=self.group_name,
                id=self.group_start_id,
                mkstream=True,
            )
        except ResponseError as error:
            if "BUSYGROUP" not in str(error):
                raise

    def consume_forever(self):
        self.start()

    def start(self, max_cycles=None):
        self.running = True
        cycles = 0

        while self.running:
            if max_cycles is not None and cycles >= max_cycles:
                break
            try:
                self.reclaim_orphans()
            except RedisError as error:
                self._log_consumer_redis_error("consumer_reclaim_failed", error)
                if not self._recover_from_nogroup(error):
                    self.sleep(self.block_ms / 1000)
                cycles += 1
                continue

            try:
                self.run_once()
            except RedisError as error:
                self._log_consumer_redis_error("consumer_poll_failed", error)
                if not self._recover_from_nogroup(error):
                    self.sleep(self.block_ms / 1000)
            finally:
                cycles += 1

    def stop(self):
        self.running = False

    @staticmethod
    def _is_nogroup_error(error):
        return "NOGROUP" in str(error)

    def _recover_from_nogroup(self, error):
        """Recreate the consumer group after a NOGROUP error so the loop
        continues instead of repeating the same failure forever (e.g. after
        the stream/group was removed or never created)."""
        if not self._is_nogroup_error(error):
            return False
        try:
            self.ensure_group()
        except RedisError as recreate_error:
            self._log_consumer_redis_error("consumer_group_recreate_failed", recreate_error)
            return False
        log_event(
            logger,
            logging.WARNING,
            "consumer_group_recreated",
            context=log_context(consumer_id=self.consumer_name),
        )
        return True

    @staticmethod
    def _normalize_xautoclaim_response(response):
        """Normalize XAUTOCLAIM responses across redis-py response shapes.

        redis-py 4.x's XAUTOCLAIM response callback (parse_xautoclaim) can
        return just the list of claimed entries (cursor discarded), while
        other/newer shapes return a (cursor, messages[, deleted_ids]) tuple.
        Detect which shape we received instead of blindly unpacking a 3-tuple.
        """
        if not response:
            return "0-0", []

        first = response[0]
        if isinstance(first, (list, tuple)):
            # Plain list-of-entries shape: no cursor is available, so this is
            # treated as the final page.
            return "0-0", list(response)

        # (cursor, messages[, deleted_ids]) shape.
        messages = response[1] if len(response) > 1 else []
        return first, messages

    def reclaim_orphans(self):
        start_id = "0-0"
        reclaimed = 0

        while True:
            response = self.redis.xautoclaim(
                name=self.stream_name,
                groupname=self.group_name,
                consumername=self.consumer_name,
                min_idle_time=self.claim_min_idle_ms,
                start_id=start_id,
                count=self.batch_size,
            )
            next_start_id, messages = self._normalize_xautoclaim_response(response)
            next_start_id = self._decode_scalar(next_start_id)
            decoded_messages = [
                (
                    self._decode_scalar(message_id),
                    self._decode_fields(fields),
                )
                for message_id, fields in messages
            ]

            for message_id, fields in decoded_messages:
                delivery_count = self._pending_delivery_count(message_id)
                if delivery_count > self.max_retries:
                    self.dead_letter(
                        message_id,
                        fields,
                        "delivery_cap_exceeded",
                        PermanentMessageError("message exceeded delivery cap"),
                        delivery_count,
                    )
                    continue
                self.handle_one(message_id, fields)
                reclaimed += 1

            if next_start_id == "0-0":
                break
            start_id = next_start_id

        return reclaimed

    def run_once(self):
        streams = self.redis.xreadgroup(
            groupname=self.group_name,
            consumername=self.consumer_name,
            streams={self.stream_name: ">"},
            count=self.batch_size,
            block=self.block_ms,
        )

        handled = 0
        for _, messages in streams or []:
            for message_id, fields in messages:
                self.handle_one(
                    self._decode_scalar(message_id),
                    self._decode_fields(fields),
                )
                handled += 1
        return handled

    def handle_one(self, message_id, fields):
        started_at = time.monotonic()
        message_context = log_context(consumer_id=self.consumer_name, stream_id=message_id)
        log_event(logger, logging.INFO, "message_received", context=message_context)

        try:
            producermessage = parse_message(fields)
        except PermanentMessageError as error:
            self._log_failure(message_context, "message_parse", started_at, error)
            self.dead_letter(message_id, fields, "validation_error", error, 1)
            return

        message_context = log_context(producermessage, **message_context)
        log_event(logger, logging.INFO, "message_parsed", context=message_context)

        processed = False
        for attempt in range(1, self.max_retries + 1):
            stage = "dedupe_processing"
            try:
                # processmessage() runs a non-idempotent pipeline (hashing,
                # document save, compression/page-calculator publish). Once
                # it has succeeded for this message, later retries within the
                # same handle_one call must only retry the batch-check /
                # notification path, not re-run processmessage.
                if not processed:
                    processmessage(producermessage, log_context_data=message_context)
                    processed = True
                stage = "batch_check"
                complete, err = isbatchcompleted(producermessage.batch)
                log_event(logger, logging.INFO, "batch_checked", context=message_context)

                if complete:
                    stage = "notification_publish"
                    redisstreamwriter().sendnotification(producermessage, err)
                    log_event(logger, logging.INFO, "notification_sent", context=message_context)
                else:
                    log_event(logger, logging.INFO, "notification_skipped", context=message_context)
            except PermanentMessageError as error:
                self._log_failure(message_context, stage, started_at, error)
                self.dead_letter(message_id, fields, "validation_error", error, attempt)
                return
            except Exception as error:
                self._log_failure(message_context, stage, started_at, error)
                if attempt == self.max_retries:
                    self.dead_letter(message_id, fields, "handler_error", error, attempt)
                    return
                self.sleep(self._retry_delay_seconds(attempt))
            else:
                self.redis.xack(self.stream_name, self.group_name, message_id)
                duration_ms = int((time.monotonic() - started_at) * 1000)
                log_event(
                    logger,
                    logging.INFO,
                    "message_completed",
                    context=message_context,
                    duration_ms=duration_ms,
                )
                return

    def dead_letter(self, message_id, fields, reason, error, delivery_count):
        self.redis.xadd(
            self.dlq_stream,
            {
                "original_message_id": message_id,
                "original_stream": self.stream_name,
                "reason": reason,
                "error": str(error)[:4000],
                "delivery_count": str(delivery_count),
                "fields": json.dumps(self._redact_dlq_fields(fields), default=str),
                "failed_at": datetime.now(timezone.utc).isoformat(),
            },
            maxlen=self.dlq_maxlen,
            approximate=True,
        )
        self.redis.xack(self.stream_name, self.group_name, message_id)

    @staticmethod
    def _redact_dlq_fields(fields):
        """Redact credential/token values before they are persisted to the
        DLQ. Every other field is preserved verbatim so failed messages can
        still be inspected/replayed."""
        if not isinstance(fields, dict):
            return fields
        return {
            key: (
                _DLQ_REDACTED_VALUE
                if str(key).lower() in _DLQ_REDACTED_FIELDS
                else value
            )
            for key, value in fields.items()
        }

    def _retry_delay_seconds(self, attempt):
        return (
            self.retry_backoff_ms / 1000 * (2 ** (attempt - 1))
            + self.jitter(attempt)
        )

    def _pending_delivery_count(self, message_id):
        # redis-py's xpending_range signature is
        # (name, groupname, idle=None, min=None, max=None, count=None,
        # consumername=None). Calling it positionally with (name, groupname,
        # message_id, message_id, 1) silently maps message_id into "idle" and
        # 1 into "max", producing the wrong XPENDING call. Use keyword
        # arguments so min/max/count land on the correct parameters.
        pending = self.redis.xpending_range(
            self.stream_name,
            self.group_name,
            min=message_id,
            max=message_id,
            count=1,
        )
        if not pending:
            return 1
        return int(pending[0].get("times_delivered", 1))

    def _log_failure(self, message_context, stage, started_at, error):
        duration_ms = int((time.monotonic() - started_at) * 1000)
        log_event(
            logger,
            logging.ERROR,
            "message_failed",
            context=message_context,
            stage=stage,
            duration_ms=duration_ms,
            exc_info=(type(error), error, error.__traceback__),
        )

    def _log_consumer_redis_error(self, event, error):
        log_event(
            logger,
            logging.ERROR,
            event,
            context=log_context(consumer_id=self.consumer_name),
            error=str(error)[:4000],
        )

    def _decode_fields(self, fields):
        return {
            self._decode_scalar(key): self._decode_scalar(value)
            for key, value in fields.items()
        }

    @staticmethod
    def _decode_scalar(value):
        if isinstance(value, bytes):
            return value.decode("utf-8")
        return value


def _default_consumer_name(consumer_id):
    return dedupe_consumer_name or consumer_id or socket.gethostname()


@app.command()
def start(consumer_id: str, start_from: StartFrom = StartFrom.beginning):
    # Default to "0" (beginning) so the first consumer group created during
    # cutover sees the existing stream backlog instead of skipping it. Pass
    # --start-from $ explicitly to start from only new records.
    initialize_compressionproducer()
    consumer = RedisDedupeConsumer(
        redis_client=redisstreamdb,
        stream_name=STREAM_KEY,
        group_name=dedupe_consumer_group,
        consumer_name=_default_consumer_name(consumer_id),
        batch_size=dedupe_consumer_batch_size,
        block_ms=dedupe_consumer_block_ms,
        max_retries=dedupe_consumer_max_retries,
        retry_backoff_ms=dedupe_consumer_retry_backoff_ms,
        claim_min_idle_ms=dedupe_consumer_claim_min_idle_ms,
        dlq_stream=dedupe_dlq_stream,
        group_start_id=start_from.value,
        dlq_maxlen=dedupe_dlq_maxlen,
    )
    consumer.ensure_group()
    consumer_context = log_context(consumer_id=consumer.consumer_name)
    log_event(logger, logging.INFO, "consumer_started", context=consumer_context)
    consumer.start()
