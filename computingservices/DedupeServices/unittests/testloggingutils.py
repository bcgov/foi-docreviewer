import json
import logging
import os
import sys
from datetime import datetime
from types import SimpleNamespace


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

psycopg2 = sys.modules.setdefault("psycopg2", SimpleNamespace(connect=lambda **kwargs: None))
psycopg2.sql = SimpleNamespace(SQL=lambda query: query)
psycopg2.DatabaseError = Exception

from utils.loggingutils import configure_logging, log_context, log_event


def test_log_event_emits_json_with_safe_context(capsys):
    configure_logging()
    logger = logging.getLogger("tests.logging")

    log_event(
        logger,
        logging.INFO,
        "message_received",
        context={
            "jobid": 11,
            "batch": "batch-1",
            "requestnumber": "LDB-123",
            "filename": "input.pdf",
            "documentmasterid": 7,
            "usertoken": "secret-token",
            "s3filepath": "s3://bucket/input.pdf",
            "payload": {"sensitive": True},
            "attributes": {"full": "document metadata"},
            "unknown_scalar": "must not be logged",
        },
    )

    output = capsys.readouterr().out
    assert len(output.splitlines()) == 1
    record = json.loads(output)

    assert record["event"] == "message_received"
    datetime.fromisoformat(record["timestamp"])
    assert record["level"] == "INFO"
    assert record["logger"] == "tests.logging"
    assert record["job_id"] == 11
    assert record["batch"] == "batch-1"
    assert record["request_number"] == "LDB-123"
    assert record["filename"] == "input.pdf"
    assert record["document_master_id"] == 7
    assert "usertoken" not in record
    assert "s3filepath" not in record
    assert "payload" not in record
    assert "attributes" not in record
    assert "unknown_scalar" not in record


def test_log_context_rejects_s3_values_regardless_of_field_name():
    class Message:
        filename = "s3://bucket/message.pdf"

    assert "filename" not in log_context(Message())
    assert "filename" not in log_context({"filename": "s3://bucket/mapping.pdf"})
    assert "filename" not in log_context(filename="s3://bucket/override.pdf")


def test_log_context_accepts_message_attributes_and_overrides_only_allowlisted_fields():
    class Message:
        jobid = 11
        requestnumber = "LDB-123"
        filename = "input.pdf"
        usertoken = "secret-token"

    context = log_context(Message(), stage="hashing", payload="secret", stream_id="1-0")

    assert context == {
        "job_id": 11,
        "request_number": "LDB-123",
        "filename": "input.pdf",
        "stage": "hashing",
        "stream_id": "1-0",
    }
    assert "usertoken" not in context
    assert "payload" not in context


def test_configure_logging_is_idempotent():
    root_logger = logging.getLogger()
    before = [handler for handler in root_logger.handlers if getattr(handler, "_dedupe_json", False)]

    configure_logging()
    configure_logging()

    after = [handler for handler in root_logger.handlers if getattr(handler, "_dedupe_json", False)]
    assert len(after) == max(1, len(before))
    assert after[0].stream is sys.stdout
