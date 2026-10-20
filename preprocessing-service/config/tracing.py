from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)

from config.settings import get_settings

_tracer_initialized = False


def init_tracing() -> None:
    """
    Initialize OpenTelemetry tracing. Safe to call multiple times (idempotent).

    There is no ASGI app to auto-instrument any more. Spans are created
    explicitly by the producer, the consumer and the CLI — see
    messaging/producer/redis_producer.py and messaging/consumer/redis_consumer.py.
    """
    global _tracer_initialized
    if _tracer_initialized:
        return

    settings = get_settings()

    resource = Resource.create(
        {
            "service.name": settings.SERVICE_NAME,
            "service.version": settings.SERVICE_VERSION,
            "deployment.environment": settings.ENVIRONMENT,
        }
    )

    provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(provider)

    # OTLP HTTP exporter (to OTEL collector)
    raw_endpoint = settings.OTEL_EXPORTER_OTLP_ENDPOINT
    endpoint = (raw_endpoint or "").strip() if raw_endpoint is not None else ""

    if endpoint and endpoint.lower() != "disabled":
        # Send spans to OTEL collector
        span_processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint))
        provider.add_span_processor(span_processor)
    elif settings.OTEL_EXPORTER_OTLP_ENDPOINT_ENABLE_FALLBACK:
        # Fallback: log spans to console (useful in dev)
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

    _tracer_initialized = True
