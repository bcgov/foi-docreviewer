import json
import pytest
from marshmallow import ValidationError
from rstreamio.message.schemas.documentspagecount import get_in_documents_pagecount_msg


@pytest.mark.parametrize("payload,expected", [
    ({"jobid": "73", "ministryrequestid": "41", "pagecount": "7"},
     {"jobid": 73, "ministryrequestid": "41", "pagecount": 7}),
    ({"pagecount": 0}, {"pagecount": 0}),
    ({}, {}),
    ({"pagecount": None, "filename": None}, {"pagecount": None, "filename": None}),
    ({"filename": "O'Brien résumé.pdf"}, {"filename": "O'Brien résumé.pdf"}),
])
def test_schema_values(payload, expected):
    assert vars(get_in_documents_pagecount_msg(json.dumps(payload))) == expected


@pytest.mark.parametrize("payload", [{"jobid": None}, {"ministryrequestid": None},
                                       {"pagecount": "broken"}, {"jobid": "oops"},
                                       {"unknown": "field"}])
def test_schema_rejections(payload):
    with pytest.raises(ValidationError):
        get_in_documents_pagecount_msg(json.dumps(payload))
