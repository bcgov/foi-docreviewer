import json
import logging
import re

import pytest
import structlog
from structlog.processors import EventRenamer

import config.logging as logging_config
from config.logging import configure_logging, get_logger, redact_sensitive_fields
from config.settings import get_settings


@pytest.fixture(autouse=True)
def restore_logging_configuration():
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    configuration = structlog.get_config().copy()
    yield
    root.handlers = handlers
    root.setLevel(level)
    structlog.configure(**configuration)
    get_settings.cache_clear()


def _sanitize(event):
    return redact_sensitive_fields(None, None, event)


@pytest.mark.parametrize(
    "untrusted",
    [
        "GET https://example.invalid/private/document.pdf?token=synthetic-secret",
        "https://example.invalid/private/document.pdf",
        "s3://synthetic-fixtures/private/document.pdf",
        "redis://worker:synthetic-password@redis:6379/1",
    ],
)
def test_uri_like_messages_are_redacted_completely(untrusted):
    assert _sanitize({"message": untrusted})["message"] == "[REDACTED]"


def test_unknown_string_fields_are_untrusted_at_every_nesting_level():
    sanitized = _sanitize(
        {
            "message": "Worker started",
            "details": "synthetic arbitrary document-derived string",
            "nested": {
                "text": "synthetic text extracted from a PDF",
                "filename": "private-document.pdf",
            },
        }
    )

    assert sanitized == {
        "message": "Worker started",
        "details": "[REDACTED]",
        "nested": {
            "text": "[REDACTED]",
            "filename": "[REDACTED]",
        },
    }


def test_only_static_application_messages_are_retained():
    assert _sanitize({"message": "Worker started"})["message"] == "Worker started"
    assert (
        _sanitize({"message": "synthetic PDF text presented as a message"})["message"]
        == "[REDACTED]"
    )


def test_explicit_low_cardinality_fields_and_numbers_are_retained():
    sanitized = _sanitize(
        {
            "message": "Preprocessing complete",
            "outcome": "text_restored",
            "dependency": "redis",
            "pages_affected": 3,
            "duration_ms": 12.5,
        }
    )

    assert sanitized == {
        "message": "Preprocessing complete",
        "outcome": "text_restored",
        "dependency": "redis",
        "pages_affected": 3,
        "duration_ms": 12.5,
    }
    assert _sanitize({"outcome": "synthetic_document_text"}) == {
        "outcome": "[REDACTED]"
    }


def test_exception_and_error_text_are_never_rendered():
    sanitized = _sanitize(
        {
            "message": "Consumer task ended with error",
            "error": "synthetic-secret in C:/private/document.pdf",
            "exception": "GET https://example.invalid/private.pdf?token=secret",
            "exc_info": RuntimeError("synthetic secret/path"),
        }
    )

    assert sanitized == {
        "message": "Consumer task ended with error",
        "error": "[REDACTED]",
        "exception": "[REDACTED]",
        "exc_info": "[UNSUPPORTED]",
    }


def test_arbitrary_object_string_representations_are_never_called():
    class HostileObject:
        def __repr__(self):
            raise AssertionError("repr must not be called")

        def __str__(self):
            raise AssertionError("str must not be called")

    assert _sanitize({"message": "Worker started", "value": HostileObject()}) == {
        "message": "Worker started",
        "value": "[UNSUPPORTED]",
    }


def test_string_is_bounded_before_sensitive_scanning(monkeypatch):
    inspected = []

    def detector(key, value):
        inspected.append((key, value))
        return value

    monkeypatch.setattr(logging_config, "_scan_trusted_string", detector)
    beyond_bound = "SENTINEL-BEYOND-INSPECTION-BOUND"
    source = "x" * logging_config._MAX_LOG_STRING_LENGTH + beyond_bound

    sanitized = logging_config._sanitize_value("stream", source, depth=1)

    assert len(inspected) == 1
    assert len(inspected[0][1]) == logging_config._MAX_LOG_STRING_LENGTH
    assert beyond_bound not in inspected[0][1]
    assert sanitized.endswith("...[TRUNCATED]")


def test_structured_collections_and_field_names_are_bounded():
    sanitized = _sanitize(
        {
            "message": "Worker started",
            "wide": list(range(100)),
            "deep": {"level": {"level": {"level": {"level": {"x": 1}}}}},
            "document text used as a field name": "must-not-appear-as-a-key",
        }
    )

    assert len(sanitized["wide"]) == 33
    assert sanitized["wide"][-1] == "[TRUNCATED]"
    assert sanitized["deep"]["level"]["level"]["level"] == "[TRUNCATED]"
    assert "document text used as a field name" not in sanitized


def test_root_width_limit_preserves_essential_fields():
    event = {f"extra_{index}": index for index in range(40)}
    event.update(
        {
            "message": "Worker started",
            "level": "info",
            "timestamp": "2026-09-06T12:34:56.000000Z",
            "trace_id": "a" * 32,
            "span_id": "b" * 16,
        }
    )

    sanitized = _sanitize(event)

    assert sanitized["message"] == "Worker started"
    assert sanitized["level"] == "info"
    assert sanitized["timestamp"] == "2026-09-06T12:34:56.000000Z"
    assert sanitized["trace_id"] == "a" * 32
    assert sanitized["span_id"] == "b" * 16
    assert sanitized["truncated_fields"] == "[TRUNCATED]"
    assert len([key for key in sanitized if key.startswith("redacted_field_")]) == 32


def _emit_wide_event(monkeypatch, *, json_logs):
    monkeypatch.setenv("JSON_LOGS", "true" if json_logs else "false")
    get_settings.cache_clear()
    configure_logging()
    get_logger("privacy-test").info(
        "Worker started",
        **{f"extra_{index}": index for index in range(40)},
        trace_id="a" * 32,
        span_id="b" * 16,
    )


def test_wide_json_log_preserves_essential_fields(monkeypatch, capsys):
    _emit_wide_event(monkeypatch, json_logs=True)
    rendered = json.loads(capsys.readouterr().out)

    assert rendered["message"] == "Worker started"
    assert rendered["level"] == "info"
    assert rendered["timestamp"]
    assert rendered["trace_id"] == "a" * 32
    assert rendered["span_id"] == "b" * 16
    assert rendered["truncated_fields"] == "[TRUNCATED]"


def test_wide_console_log_preserves_essential_fields(monkeypatch, capsys):
    _emit_wide_event(monkeypatch, json_logs=False)
    rendered = capsys.readouterr().out

    assert "Worker started" in rendered
    assert "info" in rendered
    assert "trace_id" in rendered and "a" * 32 in rendered
    assert "span_id" in rendered and "b" * 16 in rendered
    assert "truncated_fields" in rendered


def test_foreign_standard_library_record_keeps_formatter_metadata(monkeypatch, capsys):
    monkeypatch.setenv("JSON_LOGS", "true")
    get_settings.cache_clear()
    configure_logging()

    logging.getLogger("foreign-privacy-test").info("Worker started")
    rendered = json.loads(capsys.readouterr().out)

    assert rendered["message"] == "Worker started"
    assert rendered["level"] == "info"


def test_processor_order_preserves_static_message_and_redacts_event_fields():
    renamed = EventRenamer("message")(
        None,
        None,
        {
            "event": "PDF fetched from S3",
            "source_uri": "s3://synthetic-fixtures/private/document.pdf",
        },
    )

    assert _sanitize(renamed) == {
        "message": "PDF fetched from S3",
        "source_uri": "[REDACTED]",
    }


@pytest.mark.parametrize("json_logs", [True, False])
def test_current_detector_legacy_error_fields_are_safe(monkeypatch, capsys, json_logs):
    monkeypatch.setenv("JSON_LOGS", str(json_logs).lower())
    get_settings.cache_clear()
    configure_logging()
    get_logger("current-privacy").warning(
        "Handler failed",
        error="SYNTH_EXCEPTION_CONTENT SYNTH_HIDDEN_TEXT",
        legacy_payload={
            "jobid": "SYNTH_JOB",
            "usertoken": "SYNTH_TOKEN",
            "s3filepath": "https://store.invalid/private.pdf?sig=SYNTH_QUERY#SYNTH_FRAGMENT",
        },
        detectors={
            "clip_hidden_text": {"text": "SYNTH_HIDDEN_TEXT", "spans_restored": 1}
        },
        source_uri="s3://synthetic/private.pdf",
        attempt=3,
        max_retries=3,
    )
    rendered = capsys.readouterr().out
    for sentinel in (
        "SYNTH_EXCEPTION_CONTENT",
        "SYNTH_HIDDEN_TEXT",
        "SYNTH_JOB",
        "SYNTH_TOKEN",
        "SYNTH_QUERY",
        "SYNTH_FRAGMENT",
        "private.pdf",
    ):
        assert sentinel not in rendered
    assert "Handler failed" in rendered
    assert "attempt" in rendered and "max_retries" in rendered


def test_nested_operational_names_do_not_grant_string_trust():
    event = _sanitize(
        {
            "message": "Worker started",
            "legacy_payload": {"message": "Worker started", "outcome": "clean"},
        }
    )
    assert event["legacy_payload"] == {"message": "[REDACTED]", "outcome": "[REDACTED]"}


def test_foreign_exception_and_format_args_never_invoke_representation(
    monkeypatch, capsys
):
    class HostileError(Exception):
        def __str__(self):
            raise AssertionError("must not format exception")

        def __repr__(self):
            raise AssertionError("must not represent exception")

    monkeypatch.setenv("JSON_LOGS", "true")
    get_settings.cache_clear()
    configure_logging()
    error = HostileError()
    logging.getLogger("foreign").error(
        "SYNTH %s", error, exc_info=(type(error), error, None)
    )
    get_logger("structured").error(
        "Handler failed", exc_info=(type(error), error, None)
    )
    rendered = capsys.readouterr().out
    assert "SYNTH" not in rendered
    assert "Handler failed" in rendered


def test_hostile_builtin_subclasses_are_not_inspected():
    class HostileString(str):
        def __len__(self):
            raise AssertionError("must not inspect subclass")

        def __str__(self):
            raise AssertionError("must not stringify subclass")

    assert (
        _sanitize({"message": HostileString("Worker started")})["message"]
        == "[UNSUPPORTED]"
    )


def test_total_log_traversal_has_a_node_budget():
    broad = {f"branch{i}": list(range(32)) for i in range(32)}
    result = _sanitize({"message": "Worker started", "tree": broad, "level": "info"})
    assert result["message"] == "Worker started"
    assert result["level"] == "info"
    assert len(json.dumps(result)) < 4096


def test_field_name_and_large_numeric_work_are_bounded():
    result = _sanitize({"x" * 1_000_000: "SYNTH_SECRET", "count": 1 << 100_000})
    assert result["redacted_field_0"] == "[REDACTED]"
    assert result["count"] == "[TRUNCATED]"


def test_sanitizer_failure_does_not_escape(monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("SYNTH_INTERNAL_SECRET")

    monkeypatch.setattr(logging_config, "_sanitize_value", broken)
    result = _sanitize({"message": "SYNTH_SOURCE_SECRET"})
    assert result["log_sanitization_failed"]
    assert "SYNTH" not in json.dumps(result)


def test_unknown_identifier_shaped_field_names_cannot_leak_document_text():
    result = _sanitize({"message": "Worker started", "SYNTH_HIDDEN_TEXT": 1})
    assert "SYNTH_HIDDEN_TEXT" not in json.dumps(result)


def test_non_string_credentials_and_identifiers_are_not_safe_counters():
    result = _sanitize(
        {"job_id": 123456, "usertoken": 789012, "secret": True, "attempt": 3}
    )
    assert result["job_id"] == "[REDACTED]"
    assert "123456" not in json.dumps(result)
    assert "789012" not in json.dumps(result)
    assert result["attempt"] == 3


def test_operational_counters_survive_width_limit():
    event = {f"extra_{i}": i for i in range(100)}
    event.update(
        message="Handler failed", reason="handler_error", attempt=3, max_retries=3
    )
    result = _sanitize(event)
    assert result["reason"] == "handler_error"
    assert result["attempt"] == result["max_retries"] == 3


async def test_actual_legacy_consumer_failure_is_safe_in_logs(monkeypatch, capsys):
    from unittest.mock import AsyncMock

    from messaging.consumer.redis_consumer import RedisConsumer

    monkeypatch.setenv("JSON_LOGS", "true")
    get_settings.cache_clear()
    configure_logging()
    redis = AsyncMock()
    monkeypatch.setattr(
        "messaging.consumer.redis_consumer.Redis.from_url", lambda *a, **k: redis
    )
    monkeypatch.setattr(
        "messaging.consumer.redis_consumer.dispatch_event",
        AsyncMock(
            side_effect=RuntimeError(
                "SYNTH_DOCUMENT SYNTH_TOKEN https://store.invalid/a?sig=SYNTH_QUERY"
            )
        ),
    )
    consumer = RedisConsumer()
    consumer.retry_backoff_ms = 0
    await consumer._handle_one(
        "1-0",
        {
            "jobid": "SYNTH_JOB",
            "s3filepath": "s3://synthetic/input.pdf",
            "usertoken": "SYNTH_TOKEN",
        },
    )
    rendered = capsys.readouterr().out
    for sentinel in ("SYNTH_DOCUMENT", "SYNTH_TOKEN", "SYNTH_QUERY", "SYNTH_JOB"):
        assert sentinel not in rendered
    assert "Handler failed" in rendered
    assert "Message dead-lettered" in rendered
    # Do not claim that log sanitization also sanitizes the Redis DLQ payload.


@pytest.mark.parametrize("json_logs", [True, False])
def test_root_scalar_trust_never_flows_into_payloads(monkeypatch, capsys, json_logs):
    monkeypatch.setenv("JSON_LOGS", str(json_logs).lower())
    get_settings.cache_clear()
    configure_logging()
    nested = {
        "count": 867530912345,
        "duration_ms": 314159.25,
        "success": True,
        "log_sanitization_failed": False,
    }
    get_logger("scalar-privacy").info(
        "Handler failed",
        attempt=2,
        duration_ms=125.5,
        success=False,
        status_code=503,
        log_sanitization_failed=True,
        legacy_payload={"attributes": nested},
        count={"attempt": 867530912345, "nested": {"count": 867530912345}},
        details=[867530912345, True],
        value=(314159.25, False),
        attributes={867530912345, True},
    )
    rendered = capsys.readouterr().out
    assert "867530912345" not in rendered
    assert "314159.25" not in rendered
    assert nested["count"] == 867530912345  # Caller-owned data is unchanged.
    if json_logs:
        result = json.loads(rendered)
        assert result["attempt"] == 2
        assert result["duration_ms"] == 125.5
        assert result["status_code"] == 503
        assert result["success"] is False
        assert result["log_sanitization_failed"] is True
        assert set(result["legacy_payload"]["attributes"].values()) == {"[REDACTED]"}
        assert result["details"] == result["value"] == ["[REDACTED]", "[REDACTED]"]
        # Sets are unsupported; the formatter's second pass redacts the marker.
        assert result["attributes"] == "[REDACTED]"
    else:
        plain = re.sub(r"\x1b\[[0-9;]*m", "", rendered)
        for field in (
            "attempt=2",
            "duration_ms=125.5",
            "status_code=503",
            "success=False",
        ):
            assert field in plain
        assert "'success': '[REDACTED]'" in plain
        assert "'log_sanitization_failed': '[REDACTED]'" in plain


def test_root_scalar_bounds_and_hostile_numeric_subclasses():
    class HostileInt(int):
        def bit_length(self):
            raise AssertionError("must not inspect subclass")

        def __repr__(self):
            raise AssertionError("must not render subclass")

    class HostileFloat(float):
        def __float__(self):
            raise AssertionError("must not convert subclass")

        def __repr__(self):
            raise AssertionError("must not render subclass")

    assert _sanitize({"count": HostileInt(123)})["count"] == "[UNSUPPORTED]"
    assert (
        _sanitize({"duration_ms": HostileFloat(123)})["duration_ms"] == "[UNSUPPORTED]"
    )
    assert _sanitize({"count": 1 << 100_000})["count"] == "[TRUNCATED]"
    for value in (float("nan"), float("inf"), float("-inf")):
        assert _sanitize({"duration_ms": value})["duration_ms"] == "[REDACTED]"
    result = _sanitize({"nested": {"count": {"count": {"count": 867530912345}}}})
    assert "867530912345" not in json.dumps(result)
    assert _sanitize({"success": 123, "count": True}) == {
        "success": "[REDACTED]",
        "count": "[REDACTED]",
    }


@pytest.mark.parametrize("field,length", [("trace_id", 32), ("span_id", 16)])
@pytest.mark.parametrize(
    "candidate,valid",
    [
        ("aB", True),
        ("00", False),
        ("zz", False),
        ("short", False),
    ],
)
def test_trace_identifiers_require_nonzero_hex(field, length, candidate, valid):
    value = candidate * (length // 2) if candidate != "short" else "abc"
    assert _sanitize({field: value})[field] == (value if valid else "[REDACTED]")
