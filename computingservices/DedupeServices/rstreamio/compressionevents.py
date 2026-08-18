import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Mapping


@dataclass(frozen=True)
class CompressionEventDefinition:
    topic: str
    event_type: str
    schema_version: str
    source: str


@dataclass(frozen=True)
class PublishResult:
    stream_id: bytes | str
    event_id: str
    correlation_id: str
    timestamp: str


class StandardCompressionPublisher:
    def __init__(
        self,
        redis_client,
        stream_prefix: str,
        event_definition: CompressionEventDefinition,
        uuid_provider: Callable[[], object] | None = None,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self._validate_stream_prefix(stream_prefix)
        self._validate_event_definition(event_definition)

        self._redis_client = redis_client
        self._stream_prefix = stream_prefix
        self._event_definition = event_definition
        self._uuid_provider = uuid_provider or self._uuid7
        self._now_provider = now_provider or (lambda: datetime.now(timezone.utc))

    def publish(
        self, payload: Mapping[str, object], correlation_id: str | None = None
    ) -> PublishResult:
        event_id = str(self._uuid_provider())
        resolved_correlation_id = (
            correlation_id if correlation_id is not None else str(self._uuid_provider())
        )
        timestamp = self._timestamp(self._now_provider())
        envelope = {
            "event_id": event_id,
            "event_type": self._event_definition.event_type,
            "schema_version": self._event_definition.schema_version,
            "source": self._event_definition.source,
            "timestamp": timestamp,
            "correlation_id": resolved_correlation_id,
            "payload": payload,
        }
        serialized_envelope = json.dumps(
            envelope, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        stream_id = self._redis_client.xadd(
            f"{self._stream_prefix}:{self._event_definition.topic}",
            {
                "_watermill_message_uuid": event_id,
                "payload": serialized_envelope,
                "metadata": b"",
            },
        )
        return PublishResult(
            stream_id=stream_id,
            event_id=event_id,
            correlation_id=resolved_correlation_id,
            timestamp=timestamp,
        )

    @staticmethod
    def _uuid7() -> object:
        from uuid6 import uuid7

        return uuid7()

    @staticmethod
    def _timestamp(value: datetime) -> str:
        if not isinstance(value, datetime):
            raise ValueError("now_provider must return a datetime")
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("now_provider must return a timezone-aware datetime")
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _validate_stream_prefix(stream_prefix: str) -> None:
        if not isinstance(stream_prefix, str) or not stream_prefix.strip():
            raise ValueError("stream_prefix must be a non-empty string")

    @staticmethod
    def _validate_event_definition(event_definition: CompressionEventDefinition) -> None:
        if not isinstance(event_definition, CompressionEventDefinition):
            raise ValueError("event_definition must be a CompressionEventDefinition")
        for name in ("topic", "event_type", "schema_version", "source"):
            value = getattr(event_definition, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"event_definition.{name} must be a non-empty string")
