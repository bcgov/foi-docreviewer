import json
import logging
import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

psycopg2 = sys.modules.setdefault("psycopg2", SimpleNamespace(connect=lambda **kwargs: None))
psycopg2.sql = SimpleNamespace(SQL=lambda query: query)
psycopg2.DatabaseError = Exception

import rstreamio.redisstreamwriter as writer_module
from utils.loggingutils import configure_logging


class FakeNotificationStream:
    def __init__(self, result="1712345678901-0"):
        self.result = result
        self.calls = []

    def add(self, fields, id):
        self.calls.append((fields, id))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@pytest.fixture
def writer(monkeypatch):
    stream = FakeNotificationStream()
    instance = writer_module.redisstreamwriter()
    monkeypatch.setattr(instance, "notificationstream", stream)
    return instance, stream


def notification_message():
    return SimpleNamespace(
        batch="batch-1",
        ministryrequestid=42,
        createdby="user@example.com",
        usertoken="super-secret-user-token",
    )


def test_notification_success_log_is_safe_structured_json(writer, capsys):
    instance, stream = writer
    configure_logging()
    capsys.readouterr()

    instance.sendnotification(notification_message())

    records = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    record = next(record for record in records if record["event"] == "notification_published")

    assert record["batch"] == "batch-1"
    assert record["ministry_request_id"] == 42
    assert "payload" not in record
    assert "usertoken" not in record
    assert "super-secret-user-token" not in json.dumps(record)
    assert stream.calls[0][1] == "*"


def test_notification_failure_log_has_safe_ids_and_traceback(writer, capsys):
    instance, stream = writer
    stream.result = RuntimeError("redis unavailable")
    configure_logging()
    capsys.readouterr()

    instance.sendnotification(notification_message(), error=True)

    records = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    record = next(record for record in records if record["event"] == "notification_publish_failed")

    assert record["batch"] == "batch-1"
    assert record["ministry_request_id"] == 42
    assert record["exception_type"] == "RuntimeError"
    assert "super-secret-user-token" not in json.dumps(record)
