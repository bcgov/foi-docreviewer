"""
Start processing only latest records:
$ python consumer.py consumer1 --start-from $
Start processing all records in the stream from the beginning:
$ python consumer.py consumer1 --start-from 0
"""
import json
import logging
import random
import socket
import time
from datetime import datetime, timezone
from enum import Enum

import typer
from redis.exceptions import ResponseError

from utils import (
    dedupe_consumer_batch_size,
    dedupe_consumer_block_ms,
    dedupe_consumer_group,
    dedupe_consumer_max_retries,
    dedupe_consumer_name,
    dedupe_consumer_retry_backoff_ms,
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
        dlq_stream,
        sleep=None,
        jitter=None,
        group_start_id="0",
    ):
        self.redis = redis_client
        self.stream_name = stream_name
        self.group_name = group_name
        self.consumer_name = consumer_name
        self.batch_size = batch_size
        self.block_ms = block_ms
        self.max_retries = max_retries
        self.retry_backoff_ms = retry_backoff_ms
        self.dlq_stream = dlq_stream
        self.sleep = sleep or time.sleep
        self.group_start_id = group_start_id
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
        while True:
            self.run_once()

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

        for attempt in range(1, self.max_retries + 1):
            stage = "dedupe_processing"
            try:
                processmessage(producermessage, log_context_data=message_context)
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
                "fields": json.dumps(fields, default=str),
                "failed_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        self.redis.xack(self.stream_name, self.group_name, message_id)

    def _retry_delay_seconds(self, attempt):
        return (
            self.retry_backoff_ms / 1000 * (2 ** (attempt - 1))
            + self.jitter(attempt)
        )

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
def start(consumer_id: str, start_from: StartFrom = StartFrom.latest):
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
        dlq_stream=dedupe_dlq_stream,
        group_start_id=start_from.value,
    )
    consumer.ensure_group()
    consumer_context = log_context(consumer_id=consumer.consumer_name)
    log_event(logger, logging.INFO, "consumer_started", context=consumer_context)
    consumer.consume_forever()
