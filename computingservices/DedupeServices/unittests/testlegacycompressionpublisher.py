import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from rstreamio.legacycompressionpublisher import LegacyCompressionPublisher


class FakeStream:
    def __init__(self):
        self.calls = []

    def add(self, fields, id):
        self.calls.append((fields, id))
        return b"1712345678901-0"


def test_publish_converts_only_legacy_incompatible_and_attributes_fields():
    stream = FakeStream()
    payload = {
        "jobid": 11,
        "s3filepath": "s3://bucket/input.pdf",
        "filename": "input.pdf",
        "ministryrequestid": 42,
        "documentmasterid": 7,
        "trigger": "new",
        "createdby": "user@example.com",
        "requestnumber": "LDB-123",
        "batch": "batch-1",
        "incompatible": True,
        "bcgovcode": "LDB",
        "attributes": {"isattachment": True, "pages": 3},
    }

    result = LegacyCompressionPublisher(stream).publish(payload)

    assert result == b"1712345678901-0"
    assert stream.calls == [
        (
            {
                **payload,
                "incompatible": "true",
                "attributes": '{"isattachment": true, "pages": 3}',
            },
            "*",
        )
    ]
    assert payload["incompatible"] is True
    assert payload["attributes"] == {"isattachment": True, "pages": 3}


def test_publish_preserves_optional_field_presence_and_values():
    stream = FakeStream()
    payload = {
        "jobid": 11,
        "incompatible": False,
        "attributes": {},
        "documentid": 8,
        "outputdocumentmasterid": 9,
        "originaldocumentmasterid": 10,
        "usertoken": "token",
    }

    LegacyCompressionPublisher(stream).publish(payload)

    fields, stream_id = stream.calls[0]
    assert stream_id == "*"
    assert fields == {
        "jobid": 11,
        "incompatible": "false",
        "attributes": "{}",
        "documentid": 8,
        "outputdocumentmasterid": 9,
        "originaldocumentmasterid": 10,
        "usertoken": "token",
    }


def test_publish_omits_absent_optional_fields():
    stream = FakeStream()
    payload = {
        "jobid": 11,
        "incompatible": False,
        "attributes": {},
    }

    LegacyCompressionPublisher(stream).publish(payload)

    fields, stream_id = stream.calls[0]
    assert stream_id == "*"
    assert fields == {
        "jobid": 11,
        "incompatible": "false",
        "attributes": "{}",
    }
