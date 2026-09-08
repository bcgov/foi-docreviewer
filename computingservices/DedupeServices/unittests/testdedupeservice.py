import json
import logging
import os
import sys
from types import ModuleType, SimpleNamespace

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# The package initializer eagerly imports the database helper, although this
# reuse test replaces all database-facing functions before processing messages.
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
    "rstreamio.redisstreamwriter",
    collaborator_module("rstreamio.redisstreamwriter", redisstreamwriter=None),
)

import services.dedupeservice as dedupe_module
import services.foiredisdedupeconsumer as consumer_module
from utils.loggingutils import configure_logging


def source_message():
    return SimpleNamespace(
        incompatible=False,
        documentid=None,
        filename="input.pdf",
        documentmasterid=7,
        jobid=11,
        batch="batch-1",
        ministryrequestid=22,
        requestnumber="FOI-123",
    )


def logged_events(capsys):
    return [json.loads(line) for line in capsys.readouterr().out.splitlines()]


def install_successful_orchestration(monkeypatch):
    class FakeCompressionProducer:
        def producecompressionevent(self, message, jobid):
            return None

    class FakePageCalculatorProducer:
        def createpagecalculatorproducermessage(self, message, pagecount):
            return message

        def producepagecalculatorevent(self, message, pagecount, jobid):
            return None

    monkeypatch.setattr(dedupe_module, "compressionproducerservice", FakeCompressionProducer)
    monkeypatch.setattr(dedupe_module, "documentspagecalculatorproducerservice", FakePageCalculatorProducer)
    monkeypatch.setattr(dedupe_module, "recordjobstart", lambda message: None)
    monkeypatch.setattr(dedupe_module, "gets3documenthashcode", lambda message: ("hash", 3))
    monkeypatch.setattr(dedupe_module, "savedocumentdetails", lambda message, hashcode, pages: (8, True))
    monkeypatch.setattr(dedupe_module, "recordjobend", lambda *args: None)
    monkeypatch.setattr(dedupe_module, "updateredactionstatus", lambda message: None)
    monkeypatch.setattr(dedupe_module, "compressionjobstart", lambda message: 11)
    monkeypatch.setattr(dedupe_module, "pagecalculatorjobstart", lambda message: 12)
    dedupe_module._compressionproducer = None


def test_processmessage_emits_safe_orchestration_events(caplog, capsys, monkeypatch):
    """Fails if an orchestration stage stops emitting its safe structured event."""
    install_successful_orchestration(monkeypatch)
    configure_logging()
    caplog.set_level(logging.INFO)

    dedupe_module.processmessage(source_message(), log_context_data={"consumer_id": "consumer-1", "stream_id": "1-0"})

    events = logged_events(capsys)
    assert [event["event"] for event in events] == [
        "dedupe_started",
        "hash_completed",
        "document_saved",
        "compression_published",
        "page_calculator_published",
    ]
    for event in events:
        assert event["job_id"] == 11
        assert event["batch"] == "batch-1"
        assert event["ministry_request_id"] == 22
        assert event["document_master_id"] == 7
        assert event["filename"] == "input.pdf"
        assert event["request_number"] == "FOI-123"
        assert event["consumer_id"] == "consumer-1"
        assert event["stream_id"] == "1-0"


class OneMessageRedis:
    def __init__(self, message):
        self.message = message
        self.read_count = 0

    def xgroup_create(self, **kwargs):
        return True

    def xreadgroup(self, *, groupname, consumername, streams, count, block):
        self.read_count += 1
        if self.read_count == 1:
            stream_name = next(iter(streams))
            return [(stream_name, [("1-0", self.message)])]
        raise RuntimeError("stop test read loop")

    def xautoclaim(self, **kwargs):
        return ("0-0", [], [])

    def xack(self, *args):
        return 1

    def xadd(self, *args, **kwargs):
        return "dlq-1"


def test_consumer_emits_ordered_lifecycle_events_with_safe_context(caplog, capsys, monkeypatch):
    """Fails if Redis receipt is not correlated through completion."""
    install_successful_orchestration(monkeypatch)
    payload = {
        "s3filepath": "s3://private-bucket/input.pdf",
        "usertoken": "token-must-not-appear",
        "bcgovcode": "BCGOV",
        "requestnumber": "FOI-123",
        "filename": "input.pdf",
        "ministryrequestid": 22,
        "attributes": {
            "secret": "not logged",
            "document_content": "document-content-must-not-appear",
        },
        "batch": "batch-1",
        "jobid": 11,
        "documentmasterid": 7,
        "trigger": "recordupload",
        "createdby": "test",
    }
    message = {
        key.encode("utf-8"): (
            json.dumps(value) if key == "attributes" else str(value)
        ).encode("utf-8")
        for key, value in payload.items()
    }
    redis_client = OneMessageRedis(message)

    class NotificationWriter:
        def sendnotification(self, message, error):
            raise AssertionError("notification should be skipped")

    monkeypatch.setattr(consumer_module, "redisstreamdb", redis_client)
    monkeypatch.setattr(consumer_module, "isbatchcompleted", lambda batch: (False, False))
    monkeypatch.setattr(consumer_module, "redisstreamwriter", lambda: NotificationWriter())
    configure_logging()
    caplog.set_level(logging.INFO)

    with pytest.raises(RuntimeError, match="stop test read loop"):
        consumer_module.start("consumer-1")

    log_output = capsys.readouterr().out
    events = [json.loads(line) for line in log_output.splitlines()]
    assert [event["event"] for event in events] == [
        "consumer_started",
        "message_received",
        "message_parsed",
        "dedupe_started",
        "hash_completed",
        "document_saved",
        "compression_published",
        "page_calculator_published",
        "batch_checked",
        "notification_skipped",
        "message_completed",
    ]
    completed = events[-1]
    assert completed["duration_ms"] >= 0
    assert isinstance(completed["duration_ms"], int)
    assert {key: completed[key] for key in (
        "consumer_id", "stream_id", "job_id", "batch", "ministry_request_id",
        "document_master_id", "filename", "request_number",
    )} == {
        "consumer_id": "consumer-1", "stream_id": "1-0", "job_id": "11",
        "batch": "batch-1", "ministry_request_id": "22", "document_master_id": "7",
        "filename": "input.pdf", "request_number": "FOI-123",
    }
    assert all("s3filepath" not in event and "attributes" not in event for event in events)
    for sensitive_value in (
        "s3://private-bucket/input.pdf",
        "token-must-not-appear",
        "not logged",
        "document-content-must-not-appear",
    ):
        assert sensitive_value not in log_output


def test_consumer_logs_message_failure_with_duration_and_safe_context(caplog, capsys, monkeypatch):
    """Fails if a post-parse failure loses correlation or traceback metadata."""
    install_successful_orchestration(monkeypatch)
    redis_client = OneMessageRedis({})

    monkeypatch.setattr(consumer_module, "redisstreamdb", redis_client)
    monkeypatch.setattr(consumer_module.time, "sleep", lambda *_: None)
    monkeypatch.setattr(consumer_module.jsonmessageparser, "getdedupeproducermessage", lambda raw: source_message())
    monkeypatch.setattr(consumer_module, "isbatchcompleted", lambda batch: (_ for _ in ()).throw(RuntimeError("batch lookup failed")))
    configure_logging()
    caplog.set_level(logging.INFO)

    with pytest.raises(RuntimeError, match="stop test read loop"):
        consumer_module.start("consumer-1")

    log_output = capsys.readouterr().out
    events = [json.loads(line) for line in log_output.splitlines()]
    assert events[-1]["event"] == "message_failed"
    assert events[-1]["exception_type"] == "RuntimeError"
    assert sum(event["event"] == "message_failed" for event in events) == consumer_module.dedupe_consumer_max_retries
    assert caplog.records[-1].exc_info[0] is RuntimeError
    assert isinstance(events[-1]["duration_ms"], int)
    assert events[-1]["job_id"] == 11
    assert events[-1]["batch"] == "batch-1"
    assert events[-1]["ministry_request_id"] == 22
    assert events[-1]["document_master_id"] == 7
    assert events[-1]["filename"] == "input.pdf"
    assert events[-1]["request_number"] == "FOI-123"


def test_orchestration_failure_stops_consumer_before_batch_notification_or_completion(
    caplog, capsys, monkeypatch,
):
    """Fails if a Dedupe failure is mistaken for successful consumer completion."""
    install_successful_orchestration(monkeypatch)
    redis_client = OneMessageRedis({})
    recorded_ends = []
    batch_checks = []

    failed_message = source_message()
    failed_message.s3filepath = "s3://private-bucket/failed.pdf"
    failed_message.usertoken = "failed-token-must-not-appear"
    failed_message.attributes = {"document_content": "failed-document-content-must-not-appear"}
    monkeypatch.setattr(consumer_module, "redisstreamdb", redis_client)
    monkeypatch.setattr(consumer_module.time, "sleep", lambda *_: None)
    monkeypatch.setattr(consumer_module.jsonmessageparser, "getdedupeproducermessage", lambda raw: failed_message)
    monkeypatch.setattr(dedupe_module, "gets3documenthashcode", lambda message: (_ for _ in ()).throw(RuntimeError("hash failed")))
    monkeypatch.setattr(dedupe_module, "recordjobend", lambda *args: recorded_ends.append(args))
    monkeypatch.setattr(consumer_module, "isbatchcompleted", lambda batch: batch_checks.append(batch))
    configure_logging()
    caplog.set_level(logging.INFO)

    with pytest.raises(RuntimeError, match="stop test read loop"):
        consumer_module.start("consumer-1")

    log_output = capsys.readouterr().out
    events = [json.loads(line) for line in log_output.splitlines()]
    assert [event["event"] for event in events[:3]] == [
        "consumer_started", "message_received", "message_parsed",
    ]
    assert batch_checks == []
    assert recorded_ends == [(failed_message, True, "hash failed")] * consumer_module.dedupe_consumer_max_retries
    assert sum(event["event"] == "dedupe_started" for event in events) == consumer_module.dedupe_consumer_max_retries
    assert sum(event["event"] == "dedupe_failed" for event in events) == consumer_module.dedupe_consumer_max_retries
    assert sum(event["event"] == "message_failed" for event in events) == consumer_module.dedupe_consumer_max_retries
    assert "message_completed" not in [event["event"] for event in events]
    failed_event = events[-1]
    assert failed_event["stage"] == "dedupe_processing"
    assert failed_event["exception_type"] == "RuntimeError"
    assert caplog.records[-1].exc_info[0] is RuntimeError
    assert caplog.records[-1].exc_info[2] is not None
    for sensitive_value in (
        "s3://private-bucket/failed.pdf",
        "failed-token-must-not-appear",
        "failed-document-content-must-not-appear",
    ):
        assert sensitive_value not in log_output


def test_processmessage_logs_incompatible_completion(caplog, capsys, monkeypatch):
    """Fails if incompatible documents do not produce their terminal event."""
    install_successful_orchestration(monkeypatch)
    message = source_message()
    message.incompatible = True
    configure_logging()
    caplog.set_level(logging.INFO)

    dedupe_module.processmessage(message, log_context_data={"consumer_id": "consumer-1", "stream_id": "1-0"})

    events = logged_events(capsys)
    assert [event["event"] for event in events] == [
        "dedupe_started", "hash_completed", "document_saved", "incompatible_completed",
    ]


def test_consumer_logs_notification_sent(caplog, capsys, monkeypatch):
    """Fails if a completed batch omits the notification-sent lifecycle event."""
    install_successful_orchestration(monkeypatch)
    redis_client = OneMessageRedis({})
    notifications = []

    class NotificationWriter:
        def sendnotification(self, message, error):
            notifications.append((message, error))

    monkeypatch.setattr(consumer_module, "redisstreamdb", redis_client)
    monkeypatch.setattr(consumer_module.jsonmessageparser, "getdedupeproducermessage", lambda raw: source_message())
    monkeypatch.setattr(consumer_module, "isbatchcompleted", lambda batch: (True, False))
    monkeypatch.setattr(consumer_module, "redisstreamwriter", lambda: NotificationWriter())
    configure_logging()
    caplog.set_level(logging.INFO)

    with pytest.raises(RuntimeError, match="stop test read loop"):
        consumer_module.start("consumer-1")

    events = logged_events(capsys)
    assert events[-2]["event"] == "notification_sent"
    assert events[-1]["event"] == "message_completed"
    assert len(notifications) == 1


def test_consumer_logs_parser_failure_as_json_with_traceback(caplog, capsys, monkeypatch):
    """Fails if parsing errors skip the failure lifecycle event or traceback."""
    redis_client = OneMessageRedis({})

    monkeypatch.setattr(consumer_module, "initialize_compressionproducer", lambda: None)
    monkeypatch.setattr(consumer_module, "redisstreamdb", redis_client)
    monkeypatch.setattr(consumer_module.jsonmessageparser, "getdedupeproducermessage", lambda raw: (_ for _ in ()).throw(ValueError("invalid message")))
    configure_logging()
    caplog.set_level(logging.INFO)

    with pytest.raises(RuntimeError, match="stop test read loop"):
        consumer_module.start("consumer-1")

    events = logged_events(capsys)
    assert [event["event"] for event in events] == [
        "consumer_started", "message_received", "message_failed",
    ]
    assert events[-1]["exception_type"] == "PermanentMessageError"
    assert isinstance(events[-1]["duration_ms"], int)
    assert caplog.records[-1].exc_info[0] is consumer_module.PermanentMessageError


def test_processmessage_reuses_one_compression_producer_across_messages(monkeypatch):
    producer_instances = []
    compression_calls = []
    page_calculator_calls = []

    class FakeCompressionProducer:
        def __init__(self):
            producer_instances.append(self)

        def producecompressionevent(self, message, jobid):
            compression_calls.append((message, jobid))

    class FakePageCalculatorProducer:
        def createpagecalculatorproducermessage(self, message, pagecount):
            return (message, pagecount)

        def producepagecalculatorevent(self, message, pagecount, jobid):
            page_calculator_calls.append((message, pagecount, jobid))

    monkeypatch.setattr(dedupe_module, "compressionproducerservice", FakeCompressionProducer)
    monkeypatch.setattr(dedupe_module, "documentspagecalculatorproducerservice", FakePageCalculatorProducer)
    monkeypatch.setattr(dedupe_module, "recordjobstart", lambda message: None)
    monkeypatch.setattr(dedupe_module, "gets3documenthashcode", lambda message: ("hash", 3))
    monkeypatch.setattr(dedupe_module, "savedocumentdetails", lambda message, hashcode, pages: (8, True))
    monkeypatch.setattr(dedupe_module, "recordjobend", lambda *args: None)
    monkeypatch.setattr(dedupe_module, "compressionjobstart", lambda message: 11)
    monkeypatch.setattr(dedupe_module, "pagecalculatorjobstart", lambda message: 12)
    dedupe_module._compressionproducer = None

    dedupe_module.processmessage(source_message())
    dedupe_module.processmessage(source_message())

    assert len(producer_instances) == 1
    assert [jobid for _, jobid in compression_calls] == [11, 11]
    assert len(page_calculator_calls) == 2


class StartupRedis:
    def __init__(self):
        self.group_create_calls = 0
        self.read_calls = 0

    def xgroup_create(self, **kwargs):
        self.group_create_calls += 1
        return True

    def xreadgroup(self, *, groupname, consumername, streams, count, block):
        self.read_calls += 1
        raise RuntimeError("stop test read loop")

    def xautoclaim(self, **kwargs):
        return ("0-0", [], [])

    def xack(self, *args):
        return 1

    def xadd(self, *args, **kwargs):
        return "dlq-1"


def test_consumer_rejects_invalid_configuration_before_opening_or_advancing_stream(
    monkeypatch,
):
    startup_redis = StartupRedis()

    class InvalidCompressionProducer:
        def __init__(self):
            raise ValueError("compression_messaging_mode is invalid")

    monkeypatch.setattr(consumer_module, "redisstreamdb", startup_redis)
    monkeypatch.setattr(dedupe_module, "compressionproducerservice", InvalidCompressionProducer)
    dedupe_module._compressionproducer = None

    with pytest.raises(ValueError, match="compression_messaging_mode"):
        consumer_module.start("consumer-1")

    assert startup_redis.group_create_calls == 0
    assert startup_redis.read_calls == 0


def test_consumer_startup_reuses_the_initialized_producer(monkeypatch):
    startup_redis = StartupRedis()
    producer_instances = []

    class FakeCompressionProducer:
        pass

    monkeypatch.setattr(consumer_module, "redisstreamdb", startup_redis)
    monkeypatch.setattr(
        dedupe_module,
        "compressionproducerservice",
        lambda: producer_instances.append(FakeCompressionProducer()) or producer_instances[-1],
    )
    dedupe_module._compressionproducer = None

    with pytest.raises(RuntimeError, match="stop test read loop"):
        consumer_module.start("consumer-1")
    with pytest.raises(RuntimeError, match="stop test read loop"):
        consumer_module.start("consumer-1")

    assert len(producer_instances) == 1
    assert startup_redis.group_create_calls == 2
    assert startup_redis.read_calls == 2
