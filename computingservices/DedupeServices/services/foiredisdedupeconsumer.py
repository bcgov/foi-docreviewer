"""
Start processing only new records published after the consumer group is
created (default). The dedupe stream is not trimmed and message handling
is not idempotent, so replaying the whole historical stream on every fresh
group is unsafe:
$ python consumer.py consumer1
$ python consumer.py consumer1 --start-from $
Legacy checkpoint seeding is opt-in and explicit: it only happens when the
operator sets DEDUPE_LEGACY_CHECKPOINT_KEY to the exact legacy cursor key
that should be trusted (this is deliberately NOT derived from consumer_id,
because the production entrypoint invokes this CLI with the literal "$"
positional, and that value collides with the shared "$:lastid" key used by
other still-legacy services and both Dedupe deployments). When that env
var is set and a brand new group is created at the default "$", it is
seeded from that configured key if a real backlog cursor is present there.
The legacy key itself is never deleted (it may still be relied upon by
other consumers); instead a Dedupe-scoped, one-shot marker is set once the
seed has actually been used, so the same cursor is never replayed again on
a later startup. Force a full replay of the stream from the beginning only
if you explicitly need it (e.g. a one-off backfill):
$ python consumer.py consumer1 --start-from 0
"""
import json
import logging
import random
import re
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
    dedupe_legacy_checkpoint_key,
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


def _legacy_seed_marker_key(stream_name, group_name, checkpoint_key):
    """Dedupe-scoped, one-shot marker recording that a brand new consumer
    group for (stream_name, group_name) has already been seeded from the
    configured legacy checkpoint key. Namespaced under "dedupe:" and keyed
    by the full stream/group/checkpoint identity so distinct dedupe
    deployments (e.g. normal vs large-file workloads, or differently named
    consumer groups sharing the same legacy checkpoint key) never collide
    with each other, and this marker never collides with the legacy key
    itself (which is never written to or deleted by this consumer)."""
    return "dedupe:{0}:{1}:{2}:legacy_seeded".format(stream_name, group_name, checkpoint_key)


# Redis stream ids are always "<milliseconds>-<sequence>" (e.g. "1700000000000-0").
# Used to validate a legacy checkpoint value before trusting it as a real
# backlog cursor, instead of blindly handing an arbitrary string to
# XGROUP CREATE.
_STREAM_ID_PATTERN = re.compile(r"^\d+-\d+$")


def _is_valid_stream_id(value):
    return bool(_STREAM_ID_PATTERN.match(value))


def _resolve_group_start_id(
    redis_client, stream_name, group_name, legacy_checkpoint_key, requested_start_id
):
    """Resolve the id used only when creating a brand new consumer group.

    An explicit request to replay the whole stream (--start-from 0) is
    always honored as-is. Otherwise, the requested id is the safe "$"
    default. Legacy checkpoint seeding is opt-in and only attempted when
    DEDUPE_LEGACY_CHECKPOINT_KEY (legacy_checkpoint_key) is configured: the
    legacy key is never derived from consumer_id (the production entrypoint
    invokes this CLI with the literal "$" positional, so a derived key
    would collide with the shared "$:lastid" key used by other still-legacy
    services and both Dedupe deployments). When configured, seeding is only
    attempted if a Dedupe-scoped marker for this exact (stream_name,
    group_name, legacy_checkpoint_key) combination is not already present,
    so the same cutover cursor is never replayed twice. When legacy seeding
    is unset, already used, or the checkpoint is absent/malformed, "$" is
    kept so a fresh/lost group does not replay the entire, untrimmed stream
    through the non-idempotent processing pipeline.

    Returns a (resolved_start_id, legacy_seed_marker_key) tuple.
    legacy_seed_marker_key is None whenever legacy seeding was not used; the
    caller must SET it (never delete the legacy checkpoint key itself, which
    may still be relied upon by other consumers/deployments) once it has
    actually seeded a brand new group.
    """
    if requested_start_id != StartFrom.latest.value:
        return requested_start_id, None

    if not legacy_checkpoint_key:
        return requested_start_id, None

    marker_key = _legacy_seed_marker_key(stream_name, group_name, legacy_checkpoint_key)
    try:
        marker_present = bool(redis_client.exists(marker_key))
    except (RedisError, AttributeError):
        # AttributeError covers redis-like clients/fakes (e.g. in tests)
        # that do not implement EXISTS; treat that the same as "cannot
        # confirm the marker is absent" and skip seeding rather than risk
        # re-seeding at the same stale cursor.
        return requested_start_id, None

    if marker_present:
        return requested_start_id, None

    try:
        legacy_value = redis_client.get(legacy_checkpoint_key)
    except (RedisError, AttributeError):
        # AttributeError covers redis-like clients/fakes (e.g. in tests)
        # that do not implement a plain string GET; treat that the same as
        # "no legacy checkpoint" rather than failing group creation.
        return requested_start_id, None

    if legacy_value is None:
        return requested_start_id, None

    if isinstance(legacy_value, bytes):
        legacy_value = legacy_value.decode("utf-8", errors="replace")

    legacy_value = legacy_value.strip()
    if not legacy_value or not _is_valid_stream_id(legacy_value):
        # Blank or malformed values are not a usable backlog cursor and
        # must not be reported as seeded (so the caller never sets the
        # marker for a checkpoint that was not actually relied upon).
        return requested_start_id, None

    return legacy_value, marker_key


def _set_legacy_seed_marker(redis_client, marker_key, value):
    """Record that the legacy checkpoint has been used to seed a brand new
    consumer group, without touching the legacy checkpoint key itself
    (which may still be relied upon by other still-legacy consumers/
    deployments). This is a one-shot marker: a later startup for the same
    (stream_name, group_name, legacy_checkpoint_key) combination will see
    it present and resume at "$" instead of silently re-seeding from the
    same stale cursor."""
    try:
        redis_client.set(marker_key, value)
    except RedisError as error:
        log_event(
            logger,
            logging.WARNING,
            "legacy_seed_marker_set_failed",
            context=log_context(marker_key=marker_key),
            error=str(error)[:4000],
        )


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
        group_start_id=StartFrom.latest.value,
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

    def ensure_group(self, start_id=None):
        """Create the consumer group if it does not already exist.

        Returns True if a brand new group was created, False if the group
        already existed (BUSYGROUP). Callers use this to know whether it is
        safe to record a legacy checkpoint as consumed (see
        `_resolve_group_start_id`/`_set_legacy_seed_marker`): the one-shot
        marker must only be set once the checkpoint actually seeded a *new*
        group.
        """
        group_start_id = self.group_start_id if start_id is None else start_id
        try:
            self.redis.xgroup_create(
                name=self.stream_name,
                groupname=self.group_name,
                id=group_start_id,
                mkstream=True,
            )
        except ResponseError as error:
            if "BUSYGROUP" not in str(error):
                raise
            return False
        return True

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
            self.ensure_group(start_id=StartFrom.latest.value)
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
            decoded_messages = []
            for message_id, fields in messages:
                # Redis returns (None, None) placeholders for pending
                # entries that were deleted/trimmed from the stream out
                # from under XAUTOCLAIM; skip them instead of crashing on
                # None.items() below.
                if message_id is None or fields is None:
                    continue
                decoded_messages.append(
                    (
                        self._decode_scalar(message_id),
                        self._decode_fields(fields),
                    )
                )

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
def start(consumer_id: str, start_from: StartFrom = StartFrom.latest):
    # Default to "$" (latest) so a brand new/lost consumer group does not
    # replay the entire, untrimmed dedupe stream through the non-idempotent
    # processing pipeline. When creating a new group with this default and
    # DEDUPE_LEGACY_CHECKPOINT_KEY is configured, seed it from that legacy
    # checkpoint key if a real backlog cursor was left behind there and it
    # has not already been used (see _resolve_group_start_id). Leaving
    # DEDUPE_LEGACY_CHECKPOINT_KEY unset disables legacy seeding entirely.
    # Pass --start-from 0 explicitly to force a full replay of the stream
    # from the beginning.
    initialize_compressionproducer()
    resolved_start_id, legacy_seed_marker_key = _resolve_group_start_id(
        redisstreamdb,
        STREAM_KEY,
        dedupe_consumer_group,
        dedupe_legacy_checkpoint_key,
        start_from.value,
    )
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
        group_start_id=resolved_start_id,
        dlq_maxlen=dedupe_dlq_maxlen,
    )
    group_created = consumer.ensure_group()
    # The legacy checkpoint key is never deleted (other consumers/
    # deployments may still rely on it); instead record the Dedupe-scoped
    # marker once it has actually seeded a brand new group. If the group
    # already existed (BUSYGROUP), or no legacy checkpoint was used, leave
    # the marker unset so a stale/absent checkpoint is never mistaken for
    # having been consumed.
    if group_created and legacy_seed_marker_key:
        _set_legacy_seed_marker(redisstreamdb, legacy_seed_marker_key, resolved_start_id)
    consumer_context = log_context(consumer_id=consumer.consumer_name)
    log_event(logger, logging.INFO, "consumer_started", context=consumer_context)
    consumer.start()
