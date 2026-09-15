import json
from collections.abc import Mapping

from messaging.models import EventEnvelope, PdfPreprocessingRequestedEvent


class LegacyRedisMessageAdapter:
    """Convert a legacy flat Redis entry into the internal event envelope."""

    SOURCE = "foi-docreviewer.dedupe.legacy"

    def adapt(self, fields: Mapping[str, object]) -> EventEnvelope:
        if "jobid" not in fields:
            raise ValueError("legacy message is missing required field 'jobid'")
        if "s3filepath" not in fields:
            raise ValueError("legacy message is missing required field 's3filepath'")

        job_id = self._text(fields["jobid"], "jobid")
        source_uri = self._text(fields["s3filepath"], "s3filepath")
        legacy_payload = {
            self._text(key, "field name"): self._json_value(value)
            for key, value in fields.items()
        }
        return EventEnvelope.create(
            event_type="PdfPreprocessingRequested",
            payload=PdfPreprocessingRequestedEvent(
                job_id=job_id,
                source_uri=source_uri,
                legacy_payload=legacy_payload,
            ),
            correlation_id=job_id,
            source=self.SOURCE,
        )

    @staticmethod
    def _text(value: object, field: str) -> str:
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        elif isinstance(value, int) and not isinstance(value, bool):
            value = str(value)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"legacy message field '{field}' must be a non-empty string"
            )
        return value

    @staticmethod
    def _json_value(value: object) -> object:
        if isinstance(value, bytes):
            return value.decode("utf-8")
        return value
