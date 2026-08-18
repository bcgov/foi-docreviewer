import json
from typing import Mapping


class LegacyCompressionPublisher:
    def __init__(self, walrus_stream) -> None:
        self._walrus_stream = walrus_stream

    def publish(self, payload: Mapping[str, object]) -> bytes | str:
        legacy_payload = dict(payload)

        if "incompatible" in legacy_payload:
            legacy_payload["incompatible"] = str(
                legacy_payload["incompatible"]
            ).lower()
        if "attributes" in legacy_payload:
            legacy_payload["attributes"] = json.dumps(legacy_payload["attributes"])

        return self._walrus_stream.add(legacy_payload, id="*")
