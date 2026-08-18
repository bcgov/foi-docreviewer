"""Small, dependency-free helpers for safe structured service logging."""

import json
import logging
import sys
from datetime import datetime, timezone
from collections.abc import Mapping


_HANDLER_MARKER = "_dedupe_json"
_FIELD_ALIASES = {
    "jobid": "job_id",
    "job_id": "job_id",
    "batch": "batch",
    "requestnumber": "request_number",
    "request_number": "request_number",
    "filename": "filename",
    "documentmasterid": "document_master_id",
    "document_master_id": "document_master_id",
    "outputdocumentmasterid": "output_document_master_id",
    "output_document_master_id": "output_document_master_id",
    "originaldocumentmasterid": "original_document_master_id",
    "original_document_master_id": "original_document_master_id",
    "ministryrequestid": "ministry_request_id",
    "ministry_request_id": "ministry_request_id",
    "consumer_id": "consumer_id",
    "stream_id": "stream_id",
    "event_id": "event_id",
    "correlation_id": "correlation_id",
    "stage": "stage",
    "duration_ms": "duration_ms",
    "operation": "operation",
    "job_version": "job_version",
    "pagecount": "pagecount",
    "exception_type": "exception_type",
}
_MESSAGE_FIELDS = tuple(_FIELD_ALIASES)
_SENSITIVE_FIELDS = {
    "usertoken",
    "user_token",
    "s3filepath",
    "s3_filepath",
    "payload",
    "attributes",
    "document",
    "content",
}


class _JsonFormatter(logging.Formatter):
    def format(self, record):
        event = dict(getattr(record, "dedupe_event", {}))
        output = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "event": event.pop("event", record.getMessage()),
        }
        output.update(event)

        if record.exc_info and record.exc_info[0] is not None:
            output["exception_type"] = record.exc_info[0].__name__

        return json.dumps(output, separators=(",", ":"), default=str)


def _value_from(source, name):
    if isinstance(source, Mapping):
        return source.get(name)
    return getattr(source, name, None)


def _safe_value(value):
    return value is None or isinstance(value, (str, int, float, bool))


def _is_s3_path(value):
    if not isinstance(value, str):
        return False
    normalized = value.strip().lower()
    return normalized.startswith((
        "s3://",
        "s3a://",
        "arn:aws:s3:::",
        "https://s3.",
        "https://s3-",
    )) or ".s3.amazonaws.com/" in normalized


def _safe_fields(source):
    if source is None:
        return {}

    fields = {}
    for source_name in _MESSAGE_FIELDS:
        canonical_name = _FIELD_ALIASES[source_name]
        value = _value_from(source, source_name)
        if (
            value is not None
            and canonical_name not in fields
            and _safe_value(value)
            and not _is_s3_path(value)
        ):
            fields[canonical_name] = value
    return fields


def log_context(message=None, **overrides) -> dict[str, object]:
    """Return a sanitized context containing only approved scalar identifiers."""

    context = _safe_fields(message)
    for name, value in overrides.items():
        if name in _SENSITIVE_FIELDS:
            continue
        canonical_name = _FIELD_ALIASES.get(name)
        if canonical_name and value is not None and _safe_value(value) and not _is_s3_path(value):
            context[canonical_name] = value
    return context


def log_event(
    logger,
    level,
    event,
    *,
    context=None,
    stage=None,
    duration_ms=None,
    exc_info=False,
    **fields,
) -> None:
    """Emit one structured event, dropping fields outside the safe allowlist."""

    safe_event = log_context(context, stage=stage, duration_ms=duration_ms, **fields)
    safe_event["event"] = event
    logger.log(level, event, extra={"dedupe_event": safe_event}, exc_info=exc_info)


def configure_logging() -> None:
    """Configure the process-wide JSON stdout handler once."""

    root_logger = logging.getLogger()
    existing_handler = next(
        (handler for handler in root_logger.handlers if getattr(handler, _HANDLER_MARKER, False)),
        None,
    )
    if existing_handler is not None:
        existing_handler.stream = sys.stdout
        return

    handler = logging.StreamHandler(sys.stdout)
    setattr(handler, _HANDLER_MARKER, True)
    handler.setFormatter(_JsonFormatter())
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)
