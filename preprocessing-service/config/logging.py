# config/logging.py

import logging
import logging.config
import sys

import structlog
from opentelemetry import trace
from structlog.processors import EventRenamer

from config.settings import get_settings


def add_trace_context(_, __, event_dict):
    """
    Add OpenTelemetry trace_id and span_id (if present) to log records.
    """
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

    # Pre-chain processors: run before ProcessorFormatter / renderer
    pre_chain = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        add_trace_context,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        EventRenamer("message"),
    ]

    # Renderer used by ProcessorFormatter
    if json_logs:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(
            colors=True,
            event_key="message",  # 👈 important when you rename the key
        )

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "()": structlog.stdlib.ProcessorFormatter,
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
                # Root logger
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

    # Structlog: *do not* render to JSON here,
    # just prepare the dict for ProcessorFormatter
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
