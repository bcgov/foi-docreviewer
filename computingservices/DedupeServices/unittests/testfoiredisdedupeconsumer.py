import inspect
import json
import os
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, call

import pytest
from redis.exceptions import RedisError, ResponseError

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

psycopg2 = sys.modules.setdefault("psycopg2", SimpleNamespace(connect=lambda **kwargs: None))
psycopg2.sql = SimpleNamespace(SQL=lambda query: query)
psycopg2.DatabaseError = Exception


def collaborator_module(name, **attributes):
    module = ModuleType(name)
    for attribute_name, value in attributes.items():
        setattr(module, attribute_name, value)
    return module


sys.modules.setdefault(
    "services.s3documentservice",
    collaborator_module("services.s3documentservice", gets3documenthashcode=None),
)
sys.modules.setdefault(
    "services.dedupedbservice",
    collaborator_module(
        "services.dedupedbservice",
        savedocumentdetails=None,
        recordjobstart=None,
        recordjobend=None,
        updateredactionstatus=None,
        pagecalculatorjobstart=None,
        compressionjobstart=None,
        isbatchcompleted=None,
    ),
)
sys.modules.setdefault(
    "services.documentspagecalculatorservice",
    collaborator_module("services.documentspagecalculatorservice", documentspagecalculatorproducerservice=None),
)
sys.modules.setdefault(
    "services.compressionproducerservice",
    collaborator_module("services.compressionproducerservice", compressionproducerservice=None),
)
sys.modules.setdefault(
    "rstreamio.redisstreamwriter",
    collaborator_module("rstreamio.redisstreamwriter", redisstreamwriter=None),
)

import services.foiredisdedupeconsumer as consumer_module


def build_message_without(*excluded_keys):
    payload = {
        "s3filepath": "s3://bucket/input.pdf",
        "bcgovcode": "BCGOV",
        "requestnumber": "FOI-123",
        "filename": "input.pdf",
        "ministryrequestid": 22,
        "attributes": "{}",
        "batch": "batch-1",
        "jobid": 11,
        "documentmasterid": 7,
        "trigger": "recordupload",
        "createdby": "test",
        "outputdocumentmasterid": None,
        "originaldocumentmasterid": None,
        "usertoken": "token",
    }
    for key in excluded_keys:
        payload.pop(key, None)
    return payload


def valid_fields(**overrides):
    message = {
        "s3filepath": "s3://bucket/input.pdf",
        "bcgovcode": "BCGOV",
        "requestnumber": "FOI-123",
        "filename": "input.pdf",
        "ministryrequestid": "22",
        "attributes": "{}",
        "batch": "batch-1",
        "jobid": "11",
        "documentmasterid": "7",
        "trigger": "recordupload",
        "createdby": "test",
        "outputdocumentmasterid": "",
        "originaldocumentmasterid": "",
        "usertoken": "token",
        "incompatible": "false",
    }
    message.update(overrides)
    return message


def parsed_message():
    return SimpleNamespace(
        s3filepath="s3://bucket/input.pdf",
        bcgovcode="BCGOV",
        requestnumber="FOI-123",
        filename="input.pdf",
        ministryrequestid=22,
        attributes="{}",
        batch="batch-1",
        jobid=11,
        documentmasterid=7,
        trigger="recordupload",
        createdby="test",
        outputdocumentmasterid=None,
        originaldocumentmasterid=None,
        usertoken="token",
        incompatible=False,
    )


def parse_message(message):
    return consumer_module.parse_message(message)


def make_consumer(redis_client, **overrides):
    consumer_class = getattr(consumer_module, "RedisDedupeConsumer", None)
    assert consumer_class is not None, "RedisDedupeConsumer must exist"
    return consumer_class(
        redis_client=redis_client,
        stream_name="foi:dedupe",
        group_name="dedupe",
        consumer_name="consumer-1",
        batch_size=5,
        block_ms=1000,
        max_retries=3,
        retry_backoff_ms=250,
        claim_min_idle_ms=60000,
        dlq_stream="foi:dedupe.dlq",
        sleep=Mock(),
        jitter=lambda attempt: 0.0,
        **overrides,
    )


@pytest.fixture
def redis_client():
    client = Mock()
    client.xreadgroup.return_value = []
    return client


@pytest.fixture
def consumer(redis_client):
    return make_consumer(redis_client)


def test_missing_incompatible_defaults_to_false():
    message = build_message_without("incompatible")

    assert parse_message(message).incompatible is False


@pytest.mark.parametrize("value", [True, False, "true", "TRUE", "false", "FALSE"])
def test_valid_incompatible_values_are_preserved(value):
    message = build_message_without()
    message["incompatible"] = value

    assert parse_message(message).incompatible is (value is True or str(value).lower() == "true")


@pytest.mark.parametrize("value", [None, "", "yes", "0", 0, 1])
def test_explicit_invalid_incompatible_is_permanent(value):
    message = build_message_without()
    message["incompatible"] = value

    with pytest.raises(consumer_module.PermanentMessageError, match="incompatible"):
        parse_message(message)


def test_existing_group_is_not_an_error(redis_client, consumer):
    redis_client.xgroup_create.side_effect = ResponseError("BUSYGROUP Consumer Group name already exists")

    created = consumer.ensure_group()

    redis_client.xgroup_create.assert_called_once_with(
        name=consumer.stream_name,
        groupname=consumer.group_name,
        id=consumer.group_start_id,
        mkstream=True,
    )
    assert created is False


def test_ensure_group_reports_true_when_a_new_group_is_created(redis_client, consumer):
    created = consumer.ensure_group()

    assert created is True


def test_successful_message_is_acked(redis_client, consumer, monkeypatch):
    monkeypatch.setattr(consumer_module, "parse_message", Mock(return_value=parsed_message()))
    monkeypatch.setattr(consumer_module, "processmessage", Mock())
    monkeypatch.setattr(consumer_module, "isbatchcompleted", Mock(return_value=(False, False)))
    monkeypatch.setattr(
        consumer_module,
        "redisstreamwriter",
        lambda: SimpleNamespace(sendnotification=Mock(side_effect=AssertionError("notification should be skipped"))),
    )

    consumer.handle_one("1-0", valid_fields())

    redis_client.xack.assert_called_once_with(
        consumer.stream_name, consumer.group_name, "1-0"
    )
    redis_client.xadd.assert_not_called()
    assert consumer.sleep.call_count == 0


def test_missing_incompatible_reaches_processing_as_false(redis_client, consumer, monkeypatch):
    message = build_message_without("incompatible")
    assert parse_message(message).incompatible is False

    process = Mock()
    monkeypatch.setattr(consumer_module, "processmessage", process)
    monkeypatch.setattr(consumer_module, "isbatchcompleted", Mock(return_value=(False, False)))
    monkeypatch.setattr(
        consumer_module,
        "redisstreamwriter",
        lambda: SimpleNamespace(sendnotification=Mock(side_effect=AssertionError("notification should be skipped"))),
    )

    consumer.handle_one("6-0", message)

    process.assert_called_once()
    assert process.call_args.args[0].incompatible is False
    redis_client.xack.assert_called_once_with(
        consumer.stream_name, consumer.group_name, "6-0"
    )
    redis_client.xadd.assert_not_called()


def test_permanent_validation_failure_is_dead_lettered_without_retry(redis_client, consumer, monkeypatch):
    monkeypatch.setattr(
        consumer_module,
        "parse_message",
        Mock(side_effect=consumer_module.PermanentMessageError("bad incompatible")),
    )

    consumer.handle_one("2-0", valid_fields())

    redis_client.xadd.assert_called_once()
    redis_client.xack.assert_called_once_with(consumer.stream_name, consumer.group_name, "2-0")
    dlq_fields = redis_client.xadd.call_args.args[1]
    assert dlq_fields["reason"] == "validation_error"
    assert dlq_fields["delivery_count"] == "1"
    assert consumer.sleep.call_count == 0


def test_transient_failure_retries_with_backoff(redis_client, consumer, monkeypatch):
    monkeypatch.setattr(consumer_module, "parse_message", Mock(return_value=parsed_message()))
    process = Mock(side_effect=[RuntimeError("temporary"), RuntimeError("temporary"), None])
    monkeypatch.setattr(consumer_module, "processmessage", process)
    monkeypatch.setattr(consumer_module, "isbatchcompleted", Mock(return_value=(False, False)))
    monkeypatch.setattr(
        consumer_module,
        "redisstreamwriter",
        lambda: SimpleNamespace(sendnotification=Mock(side_effect=AssertionError("notification should be skipped"))),
    )

    consumer.handle_one("3-0", valid_fields())

    assert process.call_count == 3
    assert consumer.sleep.call_args_list == [call(0.25), call(0.5)]
    redis_client.xack.assert_called_once_with(consumer.stream_name, consumer.group_name, "3-0")
    redis_client.xadd.assert_not_called()


def test_retry_exhaustion_dead_letters_after_final_attempt(redis_client, consumer, monkeypatch):
    monkeypatch.setattr(consumer_module, "parse_message", Mock(return_value=parsed_message()))
    monkeypatch.setattr(
        consumer_module,
        "processmessage",
        Mock(side_effect=RuntimeError("temporary")),
    )

    consumer.handle_one("3-1", valid_fields())

    assert consumer.sleep.call_args_list == [call(0.25), call(0.5)]
    redis_client.xadd.assert_called_once()
    redis_client.xack.assert_called_once_with(consumer.stream_name, consumer.group_name, "3-1")
    dlq_fields = redis_client.xadd.call_args.args[1]
    assert dlq_fields["reason"] == "handler_error"
    assert dlq_fields["delivery_count"] == "3"


def test_dlq_failure_does_not_ack(redis_client, consumer, monkeypatch):
    monkeypatch.setattr(
        consumer_module,
        "parse_message",
        Mock(side_effect=consumer_module.PermanentMessageError("bad input")),
    )
    redis_client.xadd.side_effect = RedisError("dlq unavailable")

    with pytest.raises(RedisError):
        consumer.handle_one("4-0", valid_fields())

    redis_client.xack.assert_not_called()


def test_orphan_beyond_delivery_cap_is_dead_lettered(redis_client, consumer, monkeypatch):
    redis_client.xautoclaim.return_value = ("0-0", [("5-0", valid_fields())], [])
    redis_client.xpending_range.return_value = [{"times_delivered": consumer.max_retries + 1}]
    monkeypatch.setattr(consumer, "handle_one", Mock())

    consumer.reclaim_orphans()

    redis_client.xautoclaim.assert_called_once_with(
        name=consumer.stream_name,
        groupname=consumer.group_name,
        consumername=consumer.consumer_name,
        min_idle_time=consumer.claim_min_idle_ms,
        start_id="0-0",
        count=consumer.batch_size,
    )
    consumer.handle_one.assert_not_called()
    redis_client.xadd.assert_called_once()
    redis_client.xack.assert_called_once_with(
        consumer.stream_name,
        consumer.group_name,
        "5-0",
    )


def test_orphan_within_delivery_cap_is_reprocessed(redis_client, consumer, monkeypatch):
    redis_client.xautoclaim.return_value = ("0-0", [("6-0", valid_fields())], [])
    redis_client.xpending_range.return_value = [{"times_delivered": consumer.max_retries}]
    monkeypatch.setattr(consumer, "handle_one", Mock())

    consumer.reclaim_orphans()

    consumer.handle_one.assert_called_once_with("6-0", valid_fields())
    redis_client.xadd.assert_not_called()
    redis_client.xack.assert_not_called()


def test_reclaim_orphans_continues_after_empty_page_with_nonterminal_cursor(
    redis_client, consumer, monkeypatch
):
    redis_client.xautoclaim.side_effect = [
        ("1-0", [], []),
        ("0-0", [("7-0", valid_fields())], []),
    ]
    redis_client.xpending_range.return_value = [{"times_delivered": consumer.max_retries}]
    monkeypatch.setattr(consumer, "handle_one", Mock())

    consumer.reclaim_orphans()

    assert redis_client.xautoclaim.call_args_list == [
        call(
            name=consumer.stream_name,
            groupname=consumer.group_name,
            consumername=consumer.consumer_name,
            min_idle_time=consumer.claim_min_idle_ms,
            start_id="0-0",
            count=consumer.batch_size,
        ),
        call(
            name=consumer.stream_name,
            groupname=consumer.group_name,
            consumername=consumer.consumer_name,
            min_idle_time=consumer.claim_min_idle_ms,
            start_id="1-0",
            count=consumer.batch_size,
        ),
    ]
    consumer.handle_one.assert_called_once_with("7-0", valid_fields())


def test_polling_redis_error_does_not_exit_immediately(redis_client, consumer, monkeypatch):
    redis_client.xautoclaim.return_value = ("0-0", [], [])
    consumer.running = True
    redis_client.xreadgroup.side_effect = [RedisError("connection lost"), []]
    monkeypatch.setattr(consumer, "stop", lambda: setattr(consumer, "running", False))

    consumer.start(max_cycles=2)

    assert redis_client.xreadgroup.call_count == 2
    consumer.sleep.assert_called_once_with(consumer.block_ms / 1000)


def test_reclaim_redis_error_does_not_exit_immediately(redis_client, consumer, monkeypatch):
    consumer.running = True
    redis_client.xautoclaim.side_effect = [RedisError("claim failed"), ("0-0", [], [])]
    monkeypatch.setattr(consumer, "stop", lambda: setattr(consumer, "running", False))

    consumer.start(max_cycles=2)

    assert redis_client.xautoclaim.call_count == 2
    consumer.sleep.assert_called_once_with(consumer.block_ms / 1000)


# ---------------------------------------------------------------------------
# Contract-style tests: use fakes whose method signatures mirror the pinned
# redis-py (4.x) methods exactly, instead of a permissive Mock. A permissive
# Mock accepts any positional/keyword arguments and any return shape, so it
# does not catch calls built against the wrong redis-py signature/response
# shape. These tests fail against the previous positional xpending_range call
# and the previous 3-tuple xautoclaim unpacking.
# ---------------------------------------------------------------------------


class ContractPendingRedis:
    """Fake redis client whose xpending_range mirrors redis-py 4.x's real
    signature: (name, groupname, idle=None, min=None, max=None, count=None,
    consumername=None). A positional call of
    (stream, group, message_id, message_id, 1) binds message_id to "idle" and
    1 to "max", leaving "count" unset - this fake captures exactly that."""

    def __init__(self, entries):
        self._entries = entries
        self.calls = []

    def xpending_range(self, name, groupname, idle=None, min=None, max=None, count=None, consumername=None):
        self.calls.append(
            {
                "name": name,
                "groupname": groupname,
                "idle": idle,
                "min": min,
                "max": max,
                "count": count,
                "consumername": consumername,
            }
        )
        return self._entries


def test_pending_delivery_count_calls_xpending_range_with_keyword_min_max_count(consumer):
    fake = ContractPendingRedis([{"times_delivered": 4}])
    consumer.redis = fake

    delivery_count = consumer._pending_delivery_count("42-0")

    assert delivery_count == 4
    assert len(fake.calls) == 1
    call_kwargs = fake.calls[0]
    # These are the assertions that fail against the previous positional call
    # (stream, group, message_id, message_id, 1), which binds message_id into
    # "idle" (leaving it non-None) and leaves "count" as None.
    assert call_kwargs["min"] == "42-0"
    assert call_kwargs["max"] == "42-0"
    assert call_kwargs["count"] == 1
    assert call_kwargs["idle"] is None


def test_pending_delivery_count_signature_matches_real_redis_xpending_range():
    """Bind our call arguments against redis-py's actual xpending_range
    signature to prove they land on min/max/count, not idle/min/max."""
    import redis

    real_signature = inspect.signature(redis.Redis.xpending_range)
    bound = real_signature.bind(
        Mock(), "foi:dedupe", "dedupe", min="5-0", max="5-0", count=1
    )
    bound.apply_defaults()
    assert bound.arguments["min"] == "5-0"
    assert bound.arguments["max"] == "5-0"
    assert bound.arguments["count"] == 1
    assert bound.arguments["idle"] is None


class ContractXAutoclaimListOnlyRedis:
    """Fake redis client whose xautoclaim mimics redis-py 4.x's real response
    callback (parse_xautoclaim), which discards the cursor and returns only
    the list of claimed entries: [(message_id, fields), ...]."""

    def __init__(self, entries_pages):
        self._entries_pages = list(entries_pages)
        self.xautoclaim_calls = []
        self.xack = Mock()
        self.xadd = Mock()

    def xautoclaim(self, name, groupname, consumername, min_idle_time, start_id=0, count=None, justid=False):
        self.xautoclaim_calls.append(start_id)
        return self._entries_pages.pop(0)

    def xpending_range(self, name, groupname, idle=None, min=None, max=None, count=None, consumername=None):
        return [{"times_delivered": 1}]


def test_reclaim_orphans_handles_redis_py_4x_list_only_xautoclaim_response(consumer, monkeypatch):
    fake = ContractXAutoclaimListOnlyRedis([[("8-0", valid_fields())]])
    consumer.redis = fake
    monkeypatch.setattr(consumer, "handle_one", Mock())

    reclaimed = consumer.reclaim_orphans()

    consumer.handle_one.assert_called_once_with("8-0", valid_fields())
    assert reclaimed == 1
    # No cursor is available in this shape, so only one page is fetched.
    assert fake.xautoclaim_calls == ["0-0"]


def test_reclaim_orphans_handles_empty_list_only_xautoclaim_response(consumer, monkeypatch):
    fake = ContractXAutoclaimListOnlyRedis([[]])
    consumer.redis = fake
    monkeypatch.setattr(consumer, "handle_one", Mock())

    reclaimed = consumer.reclaim_orphans()

    consumer.handle_one.assert_not_called()
    assert reclaimed == 0
    assert fake.xautoclaim_calls == ["0-0"]


def test_reclaim_orphans_handles_two_element_cursor_tuple_response(redis_client, consumer, monkeypatch):
    """Some redis-py/Redis version combinations omit the deleted-ids element
    and return a plain (cursor, messages) 2-tuple."""
    redis_client.xautoclaim.return_value = ("0-0", [("9-0", valid_fields())])
    redis_client.xpending_range.return_value = [{"times_delivered": consumer.max_retries}]
    monkeypatch.setattr(consumer, "handle_one", Mock())

    consumer.reclaim_orphans()

    consumer.handle_one.assert_called_once_with("9-0", valid_fields())


def test_reclaim_orphans_still_handles_three_element_tuple_response(redis_client, consumer, monkeypatch):
    """The existing/newer (cursor, messages, deleted_ids) shape must keep
    working after making xautoclaim handling defensive."""
    redis_client.xautoclaim.return_value = ("0-0", [("10-0", valid_fields())], [])
    redis_client.xpending_range.return_value = [{"times_delivered": consumer.max_retries}]
    monkeypatch.setattr(consumer, "handle_one", Mock())

    consumer.reclaim_orphans()

    consumer.handle_one.assert_called_once_with("10-0", valid_fields())


def test_reclaim_orphans_skips_nil_entries_from_deleted_or_trimmed_pending(
    redis_client, consumer, monkeypatch
):
    """XAUTOCLAIM can return (None, None) placeholders for pending entries
    whose stream entry was deleted/trimmed out from under it; these must be
    skipped instead of crashing on None.items() during field decoding."""
    redis_client.xautoclaim.return_value = (
        "0-0",
        [(None, None), ("11-0", valid_fields())],
        [],
    )
    redis_client.xpending_range.return_value = [{"times_delivered": 1}]
    monkeypatch.setattr(consumer, "handle_one", Mock())

    reclaimed = consumer.reclaim_orphans()

    consumer.handle_one.assert_called_once_with("11-0", valid_fields())
    assert reclaimed == 1


# ---------------------------------------------------------------------------
# NOGROUP recovery
#
# Recovery must always recreate the group at "$" (the safe tail position),
# never at consumer.group_start_id. That configured start id is only used
# once, for the very first group creation at startup (possibly seeded from
# the legacy checkpoint or an explicit --start-from 0), and must not be
# replayed again after a mid-run NOGROUP loss.
# ---------------------------------------------------------------------------


def test_poll_nogroup_error_recreates_group_and_continues(redis_client, consumer, monkeypatch):
    redis_client.xautoclaim.return_value = ("0-0", [], [])
    consumer.running = True
    redis_client.xreadgroup.side_effect = [
        ResponseError("NOGROUP No such key 'foi:dedupe' or consumer group 'dedupe'"),
        [],
    ]
    monkeypatch.setattr(consumer, "stop", lambda: setattr(consumer, "running", False))

    consumer.start(max_cycles=2)

    redis_client.xgroup_create.assert_called_once_with(
        name=consumer.stream_name,
        groupname=consumer.group_name,
        id="$",
        mkstream=True,
    )
    assert redis_client.xreadgroup.call_count == 2
    # The NOGROUP error is recovered from directly, so the backoff sleep for
    # a generic Redis failure must not fire.
    consumer.sleep.assert_not_called()


def test_reclaim_nogroup_error_recreates_group_and_continues(redis_client, consumer, monkeypatch):
    consumer.running = True
    redis_client.xautoclaim.side_effect = [
        ResponseError("NOGROUP No such key 'foi:dedupe' or consumer group 'dedupe'"),
        ("0-0", [], []),
    ]
    monkeypatch.setattr(consumer, "stop", lambda: setattr(consumer, "running", False))

    consumer.start(max_cycles=2)

    redis_client.xgroup_create.assert_called_once_with(
        name=consumer.stream_name,
        groupname=consumer.group_name,
        id="$",
        mkstream=True,
    )
    assert redis_client.xautoclaim.call_count == 2
    consumer.sleep.assert_not_called()


def test_nogroup_recreate_failure_falls_back_to_backoff_sleep(redis_client, consumer, monkeypatch):
    redis_client.xautoclaim.return_value = ("0-0", [], [])
    consumer.running = True
    redis_client.xreadgroup.side_effect = [
        ResponseError("NOGROUP No such key 'foi:dedupe' or consumer group 'dedupe'"),
        [],
    ]
    redis_client.xgroup_create.side_effect = RedisError("redis unavailable")
    monkeypatch.setattr(consumer, "stop", lambda: setattr(consumer, "running", False))

    consumer.start(max_cycles=2)

    consumer.sleep.assert_called_once_with(consumer.block_ms / 1000)


def test_non_nogroup_redis_error_does_not_recreate_group(redis_client, consumer, monkeypatch):
    redis_client.xautoclaim.return_value = ("0-0", [], [])
    consumer.running = True
    redis_client.xreadgroup.side_effect = [RedisError("connection lost"), []]
    monkeypatch.setattr(consumer, "stop", lambda: setattr(consumer, "running", False))

    consumer.start(max_cycles=2)

    redis_client.xgroup_create.assert_not_called()
    consumer.sleep.assert_called_once_with(consumer.block_ms / 1000)


def test_nogroup_recovery_recreates_at_latest_even_with_legacy_group_start_id(
    redis_client, consumer, monkeypatch
):
    """A legacy-seeded (or explicit "0") group_start_id must only apply to
    the initial group creation, not to a mid-run NOGROUP recreation."""
    consumer.group_start_id = "42-0"
    redis_client.xautoclaim.return_value = ("0-0", [], [])
    consumer.running = True
    redis_client.xreadgroup.side_effect = [
        ResponseError("NOGROUP No such key 'foi:dedupe' or consumer group 'dedupe'"),
        [],
    ]
    monkeypatch.setattr(consumer, "stop", lambda: setattr(consumer, "running", False))

    consumer.start(max_cycles=2)

    redis_client.xgroup_create.assert_called_once_with(
        name=consumer.stream_name,
        groupname=consumer.group_name,
        id="$",
        mkstream=True,
    )
    consumer.sleep.assert_not_called()


# ---------------------------------------------------------------------------
# Default CLI start_from behaviour and legacy checkpoint seeding
#
# The production entrypoint (entrypoint.sh) always runs with the CLI
# default, so that default must never create a brand new consumer group at
# "0": the dedupe stream is not trimmed and message handling is not
# idempotent, so a default of "0" would replay the entire historical
# stream. The default instead stays "$" (latest), optionally seeded from an
# explicitly configured legacy checkpoint key (DEDUPE_LEGACY_CHECKPOINT_KEY)
# when a real backlog exists. Seeding is opt-in: it is never derived from
# consumer_id, because the production entrypoint invokes this CLI with the
# literal "$" positional, which would collide with the shared "$:lastid"
# key used by other still-legacy services and both Dedupe deployments.
# ---------------------------------------------------------------------------


def test_cli_default_start_from_is_latest_to_avoid_full_stream_replay():
    signature = inspect.signature(consumer_module.start)
    assert signature.parameters["start_from"].default == consumer_module.StartFrom.latest
    assert consumer_module.StartFrom.latest.value == "$"


def test_explicit_beginning_start_from_option_remains_available():
    assert consumer_module.StartFrom.beginning.value == "0"


def test_legacy_seed_marker_key_distinguishes_stream_group_and_checkpoint_combinations():
    # The marker must be scoped to the full (stream, group, checkpoint key)
    # identity so distinct normal-vs-large-file deployments or differently
    # named consumer groups sharing the same legacy checkpoint key never
    # collide with each other.
    key_a = consumer_module._legacy_seed_marker_key("foi:dedupe", "dedupe", "consumer1:lastid")
    key_b = consumer_module._legacy_seed_marker_key("foi:dedupe-large", "dedupe", "consumer1:lastid")
    key_c = consumer_module._legacy_seed_marker_key("foi:dedupe", "dedupe-large", "consumer1:lastid")

    assert key_a == "dedupe:foi:dedupe:dedupe:consumer1:lastid:legacy_seeded"
    assert len({key_a, key_b, key_c}) == 3


def test_resolve_group_start_id_stays_latest_when_checkpoint_key_unset():
    # An unset/empty DEDUPE_LEGACY_CHECKPOINT_KEY must disable legacy
    # seeding entirely and must never read the shared "{consumer_id}:lastid"
    # style key.
    redis_client = Mock()

    resolved, marker_key = consumer_module._resolve_group_start_id(
        redis_client, "foi:dedupe", "dedupe", "", "$"
    )

    assert resolved == "$"
    assert marker_key is None
    redis_client.get.assert_not_called()
    redis_client.exists.assert_not_called()


def test_resolve_group_start_id_stays_latest_when_no_legacy_checkpoint_exists():
    redis_client = Mock()
    redis_client.exists.return_value = 0
    redis_client.get.return_value = None

    resolved, marker_key = consumer_module._resolve_group_start_id(
        redis_client, "foi:dedupe", "dedupe", "consumer1:lastid", "$"
    )

    assert resolved == "$"
    assert marker_key is None
    redis_client.get.assert_called_once_with("consumer1:lastid")


def test_resolve_group_start_id_uses_legacy_checkpoint_when_present():
    redis_client = Mock()
    redis_client.exists.return_value = 0
    redis_client.get.return_value = b"123-4"

    resolved, marker_key = consumer_module._resolve_group_start_id(
        redis_client, "foi:dedupe", "dedupe", "consumer1:lastid", "$"
    )

    assert resolved == "123-4"
    assert marker_key == consumer_module._legacy_seed_marker_key(
        "foi:dedupe", "dedupe", "consumer1:lastid"
    )


def test_resolve_group_start_id_decodes_str_legacy_checkpoint():
    redis_client = Mock()
    redis_client.exists.return_value = 0
    redis_client.get.return_value = "123-4"

    resolved, marker_key = consumer_module._resolve_group_start_id(
        redis_client, "foi:dedupe", "dedupe", "consumer1:lastid", "$"
    )

    assert resolved == "123-4"
    assert marker_key is not None


def test_resolve_group_start_id_respects_explicit_zero_and_skips_legacy_lookup():
    redis_client = Mock()

    resolved, marker_key = consumer_module._resolve_group_start_id(
        redis_client, "foi:dedupe", "dedupe", "consumer1:lastid", "0"
    )

    assert resolved == "0"
    assert marker_key is None
    redis_client.get.assert_not_called()
    redis_client.exists.assert_not_called()


def test_resolve_group_start_id_falls_back_to_latest_on_redis_error():
    redis_client = Mock()
    redis_client.exists.return_value = 0
    redis_client.get.side_effect = RedisError("redis unavailable")

    resolved, marker_key = consumer_module._resolve_group_start_id(
        redis_client, "foi:dedupe", "dedupe", "consumer1:lastid", "$"
    )

    assert resolved == "$"
    assert marker_key is None


def test_resolve_group_start_id_falls_back_to_latest_on_blank_legacy_checkpoint():
    redis_client = Mock()
    redis_client.exists.return_value = 0
    redis_client.get.return_value = b"   "

    resolved, marker_key = consumer_module._resolve_group_start_id(
        redis_client, "foi:dedupe", "dedupe", "consumer1:lastid", "$"
    )

    assert resolved == "$"
    assert marker_key is None


def test_resolve_group_start_id_falls_back_to_latest_on_malformed_legacy_checkpoint():
    """A legacy value that is not shaped like a real Redis stream id
    ("<ms>-<seq>") must not be trusted as a backlog cursor and must not be
    reported as seeded (so the caller never sets the marker)."""
    redis_client = Mock()
    redis_client.exists.return_value = 0
    redis_client.get.return_value = b"not-a-stream-id"

    resolved, marker_key = consumer_module._resolve_group_start_id(
        redis_client, "foi:dedupe", "dedupe", "consumer1:lastid", "$"
    )

    assert resolved == "$"
    assert marker_key is None


def test_resolve_group_start_id_skips_seeding_when_marker_already_present():
    # Once the one-shot marker is present, the legacy checkpoint must not be
    # re-read/re-used, even if it still exists in Redis.
    redis_client = Mock()
    redis_client.exists.return_value = 1

    resolved, marker_key = consumer_module._resolve_group_start_id(
        redis_client, "foi:dedupe", "dedupe", "consumer1:lastid", "$"
    )

    assert resolved == "$"
    assert marker_key is None
    redis_client.get.assert_not_called()


# ---------------------------------------------------------------------------
# One-shot legacy checkpoint cutover via a Dedupe-scoped marker: the legacy
# checkpoint key configured through DEDUPE_LEGACY_CHECKPOINT_KEY is never
# deleted (it may still be relied upon by other still-legacy consumers or
# the other Dedupe deployment). Instead, a marker is set only once it has
# actually seeded a brand new consumer group, never when the group already
# existed or no legacy checkpoint was used, so a later startup cannot
# silently re-seed from a stale cursor and replay the whole post-cutover
# backlog.
# ---------------------------------------------------------------------------


def test_start_sets_legacy_seed_marker_after_successful_legacy_seeded_group_creation(monkeypatch):
    redis_client = Mock()
    redis_client.exists.return_value = 0
    redis_client.get.return_value = b"123-4"
    redis_client.xgroup_create.return_value = None

    monkeypatch.setattr(consumer_module, "redisstreamdb", redis_client)
    monkeypatch.setattr(consumer_module, "dedupe_legacy_checkpoint_key", "consumer1:lastid")
    monkeypatch.setattr(consumer_module, "initialize_compressionproducer", lambda: None)
    monkeypatch.setattr(consumer_module.RedisDedupeConsumer, "start", Mock())

    consumer_module.start("consumer1")

    redis_client.xgroup_create.assert_called_once_with(
        name=consumer_module.STREAM_KEY,
        groupname=consumer_module.dedupe_consumer_group,
        id="123-4",
        mkstream=True,
    )
    expected_marker_key = consumer_module._legacy_seed_marker_key(
        consumer_module.STREAM_KEY, consumer_module.dedupe_consumer_group, "consumer1:lastid"
    )
    redis_client.set.assert_called_once_with(expected_marker_key, "123-4")
    # The legacy checkpoint key itself must never be deleted.
    redis_client.delete.assert_not_called()


def test_start_does_not_set_legacy_seed_marker_when_group_already_exists(monkeypatch):
    redis_client = Mock()
    redis_client.exists.return_value = 0
    redis_client.get.return_value = b"123-4"
    redis_client.xgroup_create.side_effect = ResponseError(
        "BUSYGROUP Consumer Group name already exists"
    )

    monkeypatch.setattr(consumer_module, "redisstreamdb", redis_client)
    monkeypatch.setattr(consumer_module, "dedupe_legacy_checkpoint_key", "consumer1:lastid")
    monkeypatch.setattr(consumer_module, "initialize_compressionproducer", lambda: None)
    monkeypatch.setattr(consumer_module.RedisDedupeConsumer, "start", Mock())

    consumer_module.start("consumer1")

    redis_client.set.assert_not_called()
    redis_client.delete.assert_not_called()


def test_start_creates_group_at_latest_when_legacy_checkpoint_key_unset(monkeypatch):
    """With DEDUPE_LEGACY_CHECKPOINT_KEY unset (the default), startup must
    create the group at "$" without ever reading the shared
    "{consumer_id}:lastid" style key."""
    redis_client = Mock()
    redis_client.xgroup_create.return_value = None

    monkeypatch.setattr(consumer_module, "redisstreamdb", redis_client)
    monkeypatch.setattr(consumer_module, "dedupe_legacy_checkpoint_key", "")
    monkeypatch.setattr(consumer_module, "initialize_compressionproducer", lambda: None)
    monkeypatch.setattr(consumer_module.RedisDedupeConsumer, "start", Mock())

    consumer_module.start("consumer1")

    redis_client.xgroup_create.assert_called_once_with(
        name=consumer_module.STREAM_KEY,
        groupname=consumer_module.dedupe_consumer_group,
        id="$",
        mkstream=True,
    )
    redis_client.get.assert_not_called()
    redis_client.exists.assert_not_called()
    redis_client.set.assert_not_called()
    redis_client.delete.assert_not_called()


def test_start_creates_group_at_latest_when_legacy_seed_marker_already_present(monkeypatch):
    """After the one-shot marker has already been set on a previous
    startup, a subsequent startup must create the group at "$", never
    re-seeding from the same stale legacy cursor."""
    redis_client = Mock()
    redis_client.exists.return_value = 1
    redis_client.xgroup_create.return_value = None

    monkeypatch.setattr(consumer_module, "redisstreamdb", redis_client)
    monkeypatch.setattr(consumer_module, "dedupe_legacy_checkpoint_key", "consumer1:lastid")
    monkeypatch.setattr(consumer_module, "initialize_compressionproducer", lambda: None)
    monkeypatch.setattr(consumer_module.RedisDedupeConsumer, "start", Mock())

    consumer_module.start("consumer1")

    redis_client.xgroup_create.assert_called_once_with(
        name=consumer_module.STREAM_KEY,
        groupname=consumer_module.dedupe_consumer_group,
        id="$",
        mkstream=True,
    )
    redis_client.get.assert_not_called()
    redis_client.set.assert_not_called()
    redis_client.delete.assert_not_called()


def test_start_respects_explicit_start_from_zero_and_bypasses_legacy_seeding(monkeypatch):
    redis_client = Mock()
    redis_client.xgroup_create.return_value = None

    monkeypatch.setattr(consumer_module, "redisstreamdb", redis_client)
    monkeypatch.setattr(consumer_module, "dedupe_legacy_checkpoint_key", "consumer1:lastid")
    monkeypatch.setattr(consumer_module, "initialize_compressionproducer", lambda: None)
    monkeypatch.setattr(consumer_module.RedisDedupeConsumer, "start", Mock())

    consumer_module.start("consumer1", start_from=consumer_module.StartFrom.beginning)

    redis_client.xgroup_create.assert_called_once_with(
        name=consumer_module.STREAM_KEY,
        groupname=consumer_module.dedupe_consumer_group,
        id="0",
        mkstream=True,
    )
    redis_client.get.assert_not_called()
    redis_client.exists.assert_not_called()
    redis_client.set.assert_not_called()
    redis_client.delete.assert_not_called()


# ---------------------------------------------------------------------------
# DLQ redaction and bounded max length
# ---------------------------------------------------------------------------


def test_dead_letter_redacts_usertoken_and_bounds_stream_length(redis_client, consumer, monkeypatch):
    monkeypatch.setattr(
        consumer_module,
        "parse_message",
        Mock(side_effect=consumer_module.PermanentMessageError("bad input")),
    )

    consumer.handle_one("11-0", valid_fields(usertoken="super-secret-token"))

    redis_client.xadd.assert_called_once()
    dlq_args = redis_client.xadd.call_args
    dlq_fields = dlq_args.args[1]
    assert dlq_args.kwargs["maxlen"] == consumer.dlq_maxlen
    assert dlq_args.kwargs["approximate"] is True

    assert "super-secret-token" not in dlq_fields["fields"]
    replayable_fields = json.loads(dlq_fields["fields"])
    assert replayable_fields["usertoken"] == "***REDACTED***"
    # Non-credential fields required for replay must survive untouched.
    assert replayable_fields["s3filepath"] == "s3://bucket/input.pdf"
    assert replayable_fields["batch"] == "batch-1"


def test_dlq_maxlen_defaults_to_ten_thousand_when_not_overridden(redis_client):
    consumer_with_default = make_consumer(redis_client)
    assert consumer_with_default.dlq_maxlen == consumer_module.dedupe_dlq_maxlen


# ---------------------------------------------------------------------------
# Non-idempotent retry: processmessage must not re-run after it has succeeded
# ---------------------------------------------------------------------------


def test_notification_failure_after_processmessage_success_does_not_reprocess(
    redis_client, consumer, monkeypatch
):
    monkeypatch.setattr(consumer_module, "parse_message", Mock(return_value=parsed_message()))
    process = Mock()
    monkeypatch.setattr(consumer_module, "processmessage", process)
    monkeypatch.setattr(consumer_module, "isbatchcompleted", Mock(return_value=(True, False)))

    notification = Mock(side_effect=[RuntimeError("notify down"), None])
    monkeypatch.setattr(
        consumer_module,
        "redisstreamwriter",
        lambda: SimpleNamespace(sendnotification=notification),
    )

    consumer.handle_one("12-0", valid_fields())

    # processmessage only ran once, even though the overall handler retried
    # after the first notification attempt failed.
    process.assert_called_once()
    assert notification.call_count == 2
    redis_client.xack.assert_called_once_with(consumer.stream_name, consumer.group_name, "12-0")
    redis_client.xadd.assert_not_called()


def test_batch_check_retry_after_processmessage_success_does_not_reprocess(
    redis_client, consumer, monkeypatch
):
    monkeypatch.setattr(consumer_module, "parse_message", Mock(return_value=parsed_message()))
    process = Mock()
    monkeypatch.setattr(consumer_module, "processmessage", process)
    batch_check = Mock(side_effect=[RuntimeError("db down"), (False, False)])
    monkeypatch.setattr(consumer_module, "isbatchcompleted", batch_check)
    monkeypatch.setattr(
        consumer_module,
        "redisstreamwriter",
        lambda: SimpleNamespace(sendnotification=Mock(side_effect=AssertionError("notification should be skipped"))),
    )

    consumer.handle_one("13-0", valid_fields())

    process.assert_called_once()
    assert batch_check.call_count == 2
    redis_client.xack.assert_called_once_with(consumer.stream_name, consumer.group_name, "13-0")


def test_processmessage_failure_before_success_still_retries_processmessage(
    redis_client, consumer, monkeypatch
):
    monkeypatch.setattr(consumer_module, "parse_message", Mock(return_value=parsed_message()))
    process = Mock(side_effect=[RuntimeError("temporary"), None])
    monkeypatch.setattr(consumer_module, "processmessage", process)
    monkeypatch.setattr(consumer_module, "isbatchcompleted", Mock(return_value=(False, False)))
    monkeypatch.setattr(
        consumer_module,
        "redisstreamwriter",
        lambda: SimpleNamespace(sendnotification=Mock(side_effect=AssertionError("notification should be skipped"))),
    )

    consumer.handle_one("14-0", valid_fields())

    # processmessage failed on the first attempt (before ever succeeding), so
    # it must be retried.
    assert process.call_count == 2
    redis_client.xack.assert_called_once_with(consumer.stream_name, consumer.group_name, "14-0")
