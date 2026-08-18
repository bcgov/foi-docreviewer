import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Mapping


COMPRESSION_EVENT_TYPE = "document.compression.requested"
COMPRESSION_SCHEMA_VERSION = "1.0.0"
COMPRESSION_EVENT_SOURCE = "foi-docreviewer.dedupe"

_REQUIRED_PAYLOAD_TYPES = {
    "jobid": int,
    "s3filepath": str,
    "filename": str,
    "ministryrequestid": int,
    "documentmasterid": int,
    "trigger": str,
    "createdby": str,
    "requestnumber": str,
    "batch": str,
    "incompatible": bool,
    "bcgovcode": str,
    "attributes": dict,
}
_OPTIONAL_PAYLOAD_TYPES = {
    "documentid": int,
    "outputdocumentmasterid": int,
    "originaldocumentmasterid": int,
    "usertoken": str,
}


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
        self._validate_payload(payload)
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
        if event_definition.event_type != COMPRESSION_EVENT_TYPE:
            raise ValueError(
                f"event_definition.event_type must be {COMPRESSION_EVENT_TYPE!r}"
            )
        if event_definition.schema_version != COMPRESSION_SCHEMA_VERSION:
            raise ValueError(
                f"event_definition.schema_version must be {COMPRESSION_SCHEMA_VERSION!r}"
            )
        if event_definition.source != COMPRESSION_EVENT_SOURCE:
            raise ValueError(
                f"event_definition.source must be {COMPRESSION_EVENT_SOURCE!r}"
            )

    @staticmethod
    def _validate_payload(payload: Mapping[str, object]) -> None:
        if not isinstance(payload, Mapping):
            raise ValueError("payload must be a mapping")

        for name, expected_type in _REQUIRED_PAYLOAD_TYPES.items():
            if name not in payload:
                raise ValueError(f"payload.{name} is required")
            StandardCompressionPublisher._validate_payload_type(
                name,
                payload[name],
                expected_type,
            )

        for name, expected_type in _OPTIONAL_PAYLOAD_TYPES.items():
            if name in payload:
                StandardCompressionPublisher._validate_payload_type(
                    name,
                    payload[name],
                    expected_type,
                )

    @staticmethod
    def _validate_payload_type(name: str, value: object, expected_type: type) -> None:
        if expected_type is int:
            if type(value) is int:
                return
            raise ValueError(f"payload.{name} must be an integer")
        if type(value) is expected_type:
            return
        type_name = {
            bool: "boolean",
            dict: "object",
            str: "string",
        }.get(expected_type, expected_type.__name__)
        article = "an" if type_name[0] in "aeiou" else "a"
        raise ValueError(f"payload.{name} must be {article} {type_name}")
