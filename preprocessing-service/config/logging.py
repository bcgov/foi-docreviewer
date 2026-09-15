# config/logging.py

import logging
import logging.config
import math
import re
import sys

import structlog
from opentelemetry import trace
from structlog.processors import EventRenamer

from config.settings import get_settings

_REDACTED = "[REDACTED]"
_TRUNCATED = "[TRUNCATED]"
_MAX_LOG_STRING_LENGTH = 1024
_MAX_LOG_COLLECTION_ITEMS = 32
_MAX_LOG_NESTING = 4
_MAX_LOG_NODES = 128
_NUMERIC_FIELDS = frozenset(
    {
        "attempt",
        "max_retries",
        "pages_affected",
        "spans_restored",
        "port",
        "duration_ms",
        "count",
        "status_code",
    }
)
_BOOLEAN_FIELDS = frozenset({"success", "log_sanitization_failed"})

_SAFE_FIELD_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")
_SAFE_TIMESTAMP = re.compile(r"^[0-9TZ:+.-]{1,64}$")
_SAFE_TRACE_ID = re.compile(r"^[0-9a-fA-F]{32}$")
_SAFE_SPAN_ID = re.compile(r"^[0-9a-fA-F]{16}$")
_URI_LIKE = re.compile(r"(?i)\b(?:https?|redis|rediss|s3)://")

# These messages are application-owned static text. A new log message must be
# added here deliberately; dynamic document text must always be passed as an
# attribute, where string values are untrusted unless explicitly classified.
_STATIC_MESSAGES = frozenset(
    {
        "Consumer did not stop in time; cancelling",
        "Consumer group already exists",
        "Consumer group created",
        "Consumer loop exited",
        "Consumer started",
        "Consumer task died",
        "Consumer task ended with error",
        "Dispatching event",
        "Event published",
        "Failed to publish event",
        "Handler failed",
        "Health probe failed",
        "Health request failed",
        "Health server listening",
        "Job already processed; nothing to do",
        "Log event omitted after sanitization failure",
        "Message dead-lettered",
        "Message handled and acked",
        "No handler registered for event type; acking",
        "PDF fetched from S3",
        "PDF uploaded to S3",
        "Preprocessing complete",
        "Reclaimed orphaned message",
        "Redis consumer connection closed",
        "Redis error in consumer loop",
        "Redis producer connection closed",
        "Redis state client closed",
        "S3 client closed",
        "Shutting down worker",
        "Worker started",
        "Worker stopped; connections closed",
        "XAUTOCLAIM failed",
        "XREADGROUP failed",
    }
)

_MESSAGE_FIELDS = frozenset({"event", "message"})
_LOW_CARDINALITY_VALUES = {
    "dependency": frozenset({"redis", "s3"}),
    "event_type": frozenset({"PdfPreprocessingCompleted", "PdfPreprocessingRequested"}),
    "level": frozenset({"critical", "debug", "error", "info", "warning"}),
    "log_level": frozenset({"critical", "debug", "error", "info", "warning"}),
    "outcome": frozenset({"clean", "text_restored"}),
    "reason": frozenset(
        {"handler_error", "missing_field", "poison_message", "validation_error"}
    ),
}
_OPERATIONAL_NAME_FIELDS = frozenset({"consumer", "dlq", "group", "stream"})
_TRUSTED_STRING_FIELDS = (
    _MESSAGE_FIELDS
    | frozenset(_LOW_CARDINALITY_VALUES)
    | _OPERATIONAL_NAME_FIELDS
    | {"timestamp", "trace_id", "span_id"}
)
_ESSENTIAL_ROOT_FIELDS = (
    # ProcessorFormatter removes these internal values before rendering. They
    # must survive the width bound so foreign stdlib records remain loggable.
    "_record",
    "_from_structlog",
    "event",
    "message",
    "level",
    "log_level",
    "timestamp",
    "trace_id",
    "span_id",
    "event_type",
    "reason",
    "outcome",
    "dependency",
    "attempt",
    "max_retries",
    "spans_restored",
    "pages_affected",
    "port",
    "count",
    "duration_ms",
    "status_code",
    "success",
    "log_sanitization_failed",
)

# Keys can contain document text too. Unknown field names are replaced, not
# echoed merely because they happen to look like Python identifiers.
_KNOWN_FIELD_NAMES = (
    _TRUSTED_STRING_FIELDS
    | frozenset(_ESSENTIAL_ROOT_FIELDS)
    | {
        "error",
        "exception",
        "exc_info",
        "stack_info",
        "stack",
        "positional_args",
        "legacy_payload",
        "detectors",
        "clip_hidden_text",
        "jobid",
        "job_id",
        "event_id",
        "correlation_id",
        "s3filepath",
        "source_uri",
        "output_uri",
        "filename",
        "text",
        "attributes",
        "value",
        "details",
        "nested",
        "wide",
        "deep",
        "count",
        "duration_ms",
        "log_sanitization_failed",
        "truncated_fields",
    }
)


def _bound_string(value: str) -> tuple[str, bool]:
    """Copy at most the deterministic inspection prefix from a source string."""
    if len(value) <= _MAX_LOG_STRING_LENGTH:
        return value, False
    return value[:_MAX_LOG_STRING_LENGTH], True


def _scan_trusted_string(key: str, value: str) -> str:
    """Validate a bounded candidate from an explicitly trusted field."""
    if _URI_LIKE.search(value):
        return _REDACTED
    if key in _MESSAGE_FIELDS:
        return value if value in _STATIC_MESSAGES else _REDACTED
    if key in _LOW_CARDINALITY_VALUES:
        return value if value in _LOW_CARDINALITY_VALUES[key] else _REDACTED
    if key in _OPERATIONAL_NAME_FIELDS:
        return _REDACTED  # Configured names can themselves contain sensitive data.
    if key == "timestamp":
        return value if _SAFE_TIMESTAMP.fullmatch(value) else _REDACTED
    if key == "trace_id":
        return (
            value if _SAFE_TRACE_ID.fullmatch(value) and int(value, 16) else _REDACTED
        )
    if key == "span_id":
        return value if _SAFE_SPAN_ID.fullmatch(value) and int(value, 16) else _REDACTED
    return _REDACTED


def _sanitize_string(key: str, value: str) -> str:
    bounded, was_truncated = _bound_string(value)
    sanitized = _scan_trusted_string(key, bounded)
    if sanitized == _REDACTED:
        return sanitized
    if was_truncated:
        return f"{sanitized}...{_TRUNCATED}"
    return sanitized


def _safe_field_name(key, index: int) -> str:
    if (
        type(key) is str
        and len(key) <= 64
        and _SAFE_FIELD_NAME.fullmatch(key)
        and key in _KNOWN_FIELD_NAMES
    ):
        return key
    return f"redacted_field_{index}"


def _sanitize_value(key, value, depth=0, *, root=False, budget=None):
    """Only inspect built-ins; never dispatch arbitrary object methods."""
    if budget is None:
        budget = [_MAX_LOG_NODES]
    if budget[0] <= 0:
        return _TRUNCATED
    budget[0] -= 1
    # Only immediate event fields are operational metadata. Trust never flows
    # into a container, even when its key is an allowlisted counter name.
    trusted_root_scalar = depth == 1
    if type(value) is str:
        if not trusted_root_scalar or key not in _TRUSTED_STRING_FIELDS:
            return _REDACTED
        return _sanitize_string(key, value)
    if type(value) in (dict, list, tuple):
        if depth >= _MAX_LOG_NESTING:
            return _TRUNCATED
        if type(value) in (list, tuple):
            result = []
            for item in value[:_MAX_LOG_COLLECTION_ITEMS]:
                if budget[0] <= 0:
                    break
                result.append(_sanitize_value("", item, depth + 1, budget=budget))
            if len(value) > len(result):
                result.append(_TRUNCATED)
            return result
        result = {}
        if root:
            for field in _ESSENTIAL_ROOT_FIELDS:
                if field in value:
                    # ProcessorFormatter removes this metadata before render.
                    if field in ("_record", "_from_structlog"):
                        result[field] = value[field]
                    else:
                        result[field] = _sanitize_value(
                            field, value[field], depth + 1, budget=budget
                        )
        additional = 0
        for index, (field, item) in enumerate(value.items()):
            if type(field) is str and root and field in _ESSENTIAL_ROOT_FIELDS:
                continue
            if additional >= _MAX_LOG_COLLECTION_ITEMS or budget[0] <= 0:
                result["truncated_fields"] = _TRUNCATED
                break
            safe_key = _safe_field_name(field, index)
            result[safe_key] = _sanitize_value(safe_key, item, depth + 1, budget=budget)
            additional += 1
        return result
    if value is None:
        return value
    if type(value) is bool:
        return value if trusted_root_scalar and key in _BOOLEAN_FIELDS else _REDACTED
    if type(value) is int:
        if not trusted_root_scalar or key not in _NUMERIC_FIELDS:
            return _REDACTED
        return value if value.bit_length() <= 64 else _TRUNCATED
    if type(value) is float:
        if not trusted_root_scalar or key not in _NUMERIC_FIELDS:
            return _REDACTED
        return value if math.isfinite(value) else _REDACTED
    return "[UNSUPPORTED]"


def redact_sensitive_fields(_, __, event_dict):
    """Fail closed for content, fail open for processing."""
    try:
        if type(event_dict) is not dict:
            return {"message": "Log event omitted after sanitization failure"}
        return _sanitize_value("log_event", event_dict, root=True)
    except Exception:
        return {
            "message": "Log event omitted after sanitization failure",
            "log_sanitization_failed": True,
        }


class SafeProcessorFormatter(structlog.stdlib.ProcessorFormatter):
    """Guard foreign logging before getMessage/exception formatting.

    Copy fixed metadata only; never interpolate args or format exceptions.
    The original LogRecord is not mutated.
    """

    def format(self, record):
        try:
            is_structlog = (
                getattr(record, "_logger", None) is not None
                and getattr(record, "_name", None) is not None
                and type(record.msg) is dict
            )
            if is_structlog:
                message = redact_sensitive_fields(None, None, record.msg)
            else:
                message = (
                    _sanitize_string("message", record.msg)
                    if type(record.msg) is str and not record.args
                    else _REDACTED
                )
            level = record.levelno if type(record.levelno) is int else logging.INFO
            if level not in (10, 20, 30, 40, 50):
                level = logging.INFO
            safe_record = logging.LogRecord(
                "preprocessing", level, "", 0, message, (), None
            )
            if is_structlog:
                safe_record._logger = record._logger
                safe_record._name = record._name
            return super().format(safe_record)
        except Exception:
            return '{"message":"Log event omitted after sanitization failure"}'


def add_trace_context(_, __, event_dict):
    """Add OpenTelemetry trace_id and span_id when a valid span is active."""
    span = trace.get_current_span()
    span_ctx = span.get_span_context() if span is not None else None

    if span_ctx and span_ctx.is_valid:
        event_dict["trace_id"] = format(span_ctx.trace_id, "032x")
        event_dict["span_id"] = format(span_ctx.span_id, "016x")

    return event_dict


def configure_logging() -> None:
    settings = get_settings()

    log_level = settings.LOG_LEVEL.upper()
    json_logs = settings.JSON_LOGS

    pre_chain = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        add_trace_context,
        EventRenamer("message"),
        redact_sensitive_fields,
    ]

    if json_logs:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(
            colors=True,
            event_key="message",
        )

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "()": SafeProcessorFormatter,
                    "processor": renderer,
                    "foreign_pre_chain": pre_chain,
                }
            },
            "handlers": {
                "default": {
                    "class": "logging.StreamHandler",
                    "stream": sys.stdout,
                    "formatter": "default",
                }
            },
            "loggers": {
                "": {
                    "handlers": ["default"],
                    "level": log_level,
                    "propagate": True,
                },
                "uvicorn.error": {
                    "handlers": ["default"],
                    "level": log_level,
                    "propagate": False,
                },
                "uvicorn.access": {
                    "handlers": ["default"],
                    "level": log_level,
                    "propagate": False,
                },
            },
        }
    )

    structlog.configure(
        processors=pre_chain
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        context_class=dict,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str):
    return structlog.get_logger(name)
