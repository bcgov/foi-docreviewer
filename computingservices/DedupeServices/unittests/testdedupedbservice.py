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

from services import dedupedbservice
from utils.loggingutils import configure_logging


class Cursor:
    def __init__(self, *, fail=False):
        self.fail = fail
        self.closed = False

    def execute(self, *_args):
        if self.fail:
            raise RuntimeError("database unavailable")

    def fetchone(self):
        return (41,)

    def close(self):
        self.closed = True


class Connection:
    def __init__(self, *, fail=False):
        self.cursor_instance = Cursor(fail=fail)
        self.commits = 0
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.commits += 1

    def close(self):
        self.closed = True


def message():
    return SimpleNamespace(
        jobid=11,
        batch="batch-1",
        ministryrequestid=22,
        documentmasterid=7,
        outputdocumentmasterid=None,
        originaldocumentmasterid=None,
        filename="input.pdf",
        requestnumber="FOI-123",
        trigger="recordupload",
        incompatible=False,
        attributes={"secret": "not logged"},
        usertoken="do-not-log",
    )


def logged_events(capsys):
    return [json.loads(line) for line in capsys.readouterr().out.splitlines()]


def test_savedocumentdetails_logs_safe_success_event(capsys, monkeypatch):
    connection = Connection()
    monkeypatch.setattr(dedupedbservice, "getdbconnection", lambda: connection)
    configure_logging()

    assert dedupedbservice.savedocumentdetails(message(), "hash", 3) == (41, True)

    event = logged_events(capsys)[-1]
    assert event["event"] == "database_recorded"
    assert event["operation"] == "save_document_details"
    assert event["document_master_id"] == 7
    assert event["filename"] == "input.pdf"
    assert event["request_number"] == "FOI-123"
    assert "attributes" not in event
    assert "usertoken" not in event
    assert connection.commits == 3
    assert connection.closed


def test_recordjobstart_logs_duplicate_at_warning(capsys, monkeypatch):
    connection = Connection()
    monkeypatch.setattr(dedupedbservice, "getdbconnection", lambda: connection)
    monkeypatch.setattr(dedupedbservice, "__doesjobversionexists", lambda *_args: True)
    configure_logging()

    dedupedbservice.recordjobstart(message())

    event = logged_events(capsys)[-1]
    assert event["event"] == "duplicate_job"
    assert event["level"] == "WARNING"
    assert event["operation"] == "record_job_start"
    assert event["job_id"] == 11
    assert event["batch"] == "batch-1"
    assert event["job_version"] == 2


def test_database_failure_logs_operation_and_reraises(capsys, caplog, monkeypatch):
    connection = Connection(fail=True)
    monkeypatch.setattr(dedupedbservice, "getdbconnection", lambda: connection)
    configure_logging()
    caplog.set_level(logging.INFO)

    with pytest.raises(RuntimeError, match="database unavailable"):
        dedupedbservice.savedocumentdetails(message(), "hash")

    event = logged_events(capsys)[-1]
    assert event["event"] == "database_operation_failed"
    assert event["operation"] == "save_document_details"
    assert event["stage"] == "write"
    assert event["exception_type"] == "RuntimeError"
    assert caplog.records[-1].exc_info[0] is RuntimeError
    assert "attributes" not in event
    assert "usertoken" not in event
