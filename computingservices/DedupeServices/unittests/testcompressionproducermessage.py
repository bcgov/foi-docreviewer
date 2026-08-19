import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from models.compressionproducermessage import compressionproducermessage


def source_message(**overrides):
    values = {
        "s3filepath": "s3://bucket/input.pdf",
        "filename": "input.pdf",
        "ministryrequestid": "42",
        "documentmasterid": "7",
        "trigger": "new",
        "createdby": "user@example.com",
        "requestnumber": "LDB-123",
        "batch": "batch-1",
        "incompatible": False,
        "usertoken": None,
        "bcgovcode": "LDB",
        "attributes": {"isattachment": True, "pages": 3},
        "documentid": None,
        "outputdocumentmasterid": None,
        "originaldocumentmasterid": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_to_dict_returns_json_native_contract_values():
    message = compressionproducermessage(11, source_message(incompatible=True))

    assert message.to_dict() == {
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


@pytest.mark.parametrize(
    ("redis_value", "expected"),
    [
        (True, True),
        (False, False),
        ("true", True),
        ("TRUE", True),
        ("False", False),
    ],
)
def test_to_dict_decodes_incompatible_from_redis_values(redis_value, expected):
    message = compressionproducermessage(
        11,
        source_message(incompatible=redis_value),
    )

    assert message.to_dict()["incompatible"] is expected


@pytest.mark.parametrize("redis_value", ["", "yes", "0", 0, None])
def test_to_dict_rejects_invalid_incompatible_values(redis_value):
    with pytest.raises(ValueError, match="incompatible"):
        compressionproducermessage(11, source_message(incompatible=redis_value))


def test_to_dict_omits_none_optional_fields():
    message = compressionproducermessage(11, source_message())

    payload = message.to_dict()

    assert "documentid" not in payload
    assert "outputdocumentmasterid" not in payload
    assert "originaldocumentmasterid" not in payload
    assert "usertoken" not in payload


def test_to_dict_preserves_present_optional_values_as_native_values():
    message = compressionproducermessage(
        11,
        source_message(
            usertoken="token",
            documentid="8",
            outputdocumentmasterid="9",
            originaldocumentmasterid="10",
        ),
    )

    payload = message.to_dict()

    assert payload["documentid"] == 8
    assert payload["outputdocumentmasterid"] == 9
    assert payload["originaldocumentmasterid"] == 10
    assert payload["usertoken"] == "token"


def test_to_dict_is_an_explicit_allowlist_not_object_dict():
    message = compressionproducermessage(11, source_message())
    message.internal_only = "not part of the contract"

    payload = message.to_dict()

    assert "internal_only" not in payload
