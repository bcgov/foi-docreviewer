"""Real PostgreSQL regression checks for SQLAlchemy compatibility."""

import pytest
from sqlalchemy import text
from reviewer_api.models.Annotations import Annotation
from reviewer_api.models.Documents import Document
from reviewer_api.models.DocumentMaster import DocumentMaster
from reviewer_api.models.RedactionLayers import RedactionLayer


@pytest.fixture
def records(session):
    session.add(
        RedactionLayer(
            redactionlayerid=910, name="Upgrade", description="Synthetic", isactive=True
        )
    )
    session.add(
        DocumentMaster(
            documentmasterid=910001,
            filepath="https://storage/bucket/00000000-0000-0000-0000-000000000001/test.pdf",
            ministryrequestid=910,
            isredactionready=True,
        )
    )
    session.flush()
    session.add(
        Document(
            documentid=910001,
            version=1,
            filename="test.pdf",
            documentmasterid=910001,
            foiministryrequestid=910,
            attributes={},
            createdby={},
            statusid=1,
            incompatible=False,
        )
    )
    session.commit()
    return session


def test_annotation_upsert_preserves_xml_and_type(records):
    xml = '<redact page="0" rect="1,2,3,4" />'
    result = Annotation.saveannotations(
        [dict(name="upgrade-annot", docid=910001, docversion=1, xml=xml, page=0)],
        910,
        {"userid": "synthetic@idir"},
    )
    assert result is not None and result.success
    row = records.execute(
        text(
            "SELECT annotation, annotationtype FROM \"Annotations\" WHERE annotationname='upgrade-annot' AND isactive=true"
        )
    ).first()
    assert row is not None and tuple(row) == (xml, "redact")
    updated = '<highlight page="0" />'
    result = Annotation.saveannotations(
        [dict(name="upgrade-annot", docid=910001, docversion=1, xml=updated, page=0)],
        910,
        {"userid": "synthetic@idir"},
    )
    assert result is not None and result.success
    rows = records.execute(
        text(
            "SELECT annotation, annotationtype FROM \"Annotations\" WHERE annotationname='upgrade-annot' AND isactive=true"
        )
    ).fetchall()
    assert [tuple(row) for row in rows] == [(updated, "highlight")]


def test_raw_annotation_read_preserves_named_fields(records):
    records.add(
        Annotation(
            annotationname="read",
            version=1,
            documentid=910001,
            documentversion=1,
            annotation='<redact page="0" />',
            annotationtype="redact",
            pagenumber=0,
            isactive=True,
            redactionlayerid=910,
            createdby={},
        )
    )
    records.commit()
    rows = Annotation.getrequestannotations(910, [910])
    assert len(rows) == 1
    assert rows[0]["annotationname"] == "read"
    assert rows[0]["documentid"] == 910001
    assert rows[0]["annotation"] == '<redact page="0" />'


def test_pagination_preserves_requested_size_and_meta(records):
    records.execute(
        text(
            "INSERT INTO \"Annotations\" (version,annotationname,documentid,documentversion,annotation,annotationtype,pagenumber,isactive,redactionlayerid,createdby,created_at) SELECT 1,'page-'||n,910001,1,'<redact />','redact',n,true,910,'{}',now() FROM generate_series(1,150) AS n"
        )
    )
    records.commit()
    result = Annotation.get_request_annotations_pagination(910, [910], 1, 3500)
    assert result.total == 150 and len(result.items) == 150
    assert result.per_page == 3500 and result.pages == 1


@pytest.mark.xfail(
    strict=True,
    reason="Baseline getdocuments uses Python and/or on SQL expressions; outside runtime compatibility scope",
)
def test_document_list_does_not_swallow_baseline_boolean_error(records):
    # No attribute row: old query legitimately returns [], not None from its error handler.
    assert Document.getdocuments(910) == []


def test_document_case_query_preserves_selected_path(records):
    assert Document.getdocumentsbyids([910001]) == {
        910001: "https://storage/bucket/00000000-0000-0000-0000-000000000001/test.pdf"
    }


def test_layer_mapping_and_deleted_replacement_filters(records):
    from reviewer_api.models.DocumentDeleted import DocumentDeleted

    records.add(
        RedactionLayer(
            redactionlayerid=911, name="Other", description="Synthetic", isactive=True
        )
    )
    records.add(
        DocumentMaster(
            documentmasterid=910002,
            filepath="https://storage/bucket/00000000-0000-0000-0000-000000000002/test.pdf",
            ministryrequestid=910,
            processingparentid=910001,
            isredactionready=True,
        )
    )
    records.flush()
    records.add(
        Document(
            documentid=910002,
            version=1,
            filename="replacement.pdf",
            documentmasterid=910002,
            foiministryrequestid=910,
            attributes={},
            createdby={},
            statusid=1,
            incompatible=False,
        )
    )
    records.flush()
    for name, document, layer, active in [
        ("old", 910001, 910, True),
        ("replacement", 910002, 910, True),
        ("other-layer", 910002, 911, True),
        ("inactive", 910002, 910, False),
    ]:
        records.add(
            Annotation(
                annotationname=name,
                version=1,
                documentid=document,
                documentversion=1,
                annotation="<redact />",
                annotationtype="redact",
                pagenumber=0,
                isactive=active,
                redactionlayerid=layer,
                createdby={},
            )
        )
    records.commit()
    result = Annotation.get_request_annotations_pagination(910, [910], 1, 3500)
    assert [(row.documentid, row.annotation) for row in result.items] == [
        (910002, "<redact />")
    ]
    records.add(
        DocumentDeleted(
            filepath="00000000-0000-0000-0000-000000000002",
            ministryrequestid=910,
            deleted=True,
        )
    )
    records.commit()
    assert (
        Annotation.get_request_annotations_pagination(910, [910], 1, 3500).items == []
    )


def test_nonempty_document_master_retains_mapping_fields(records):
    from reviewer_api.models.DocumentAttributes import DocumentAttributes

    records.add(
        DocumentAttributes(
            version=1,
            documentmasterid=910001,
            attributes={"lastmodified": "2026-01-01"},
            isactive=True,
            createdby={},
        )
    )
    records.commit()
    rows = DocumentMaster.getdocumentmaster(910)
    assert len(rows) == 1
    assert rows[0]["documentmasterid"] == 910001
    assert rows[0]["attributes"] == {"lastmodified": "2026-01-01"}
    assert rows[0]["attachmentof"] is None and rows[0]["duplicate_of"] is None


def test_nonempty_pageflag_rest_and_date_null_serialization(records, client, identity):
    import json
    from datetime import datetime
    from reviewer_api.models.DocumentPageflags import DocumentPageflag

    records.add(
        DocumentPageflag(
            foiministryrequestid=910,
            documentid=910001,
            documentversion=1,
            redactionlayerid=1,
            pageflag=json.dumps([{"page": 1, "flagid": 2}]),
            created_at=datetime(2026, 1, 2, 3, 4, 5),
            attributes=None,
            updated_at=None,
        )
    )
    records.commit()
    rows = DocumentPageflag.getpageflag_by_request_documentids(910, [1], [910001])
    assert rows == [
        {
            "documentid": 910001,
            "documentversion": 1,
            "pageflag": [{"page": 1, "flagid": 2}],
        }
    ]
    value = DocumentPageflag.getpageflag(910, 910001, 1, [1])
    assert value["created_at"] == "2026-01-02T03:04:05+00:00"
    assert value["updated_at"] is None and value["attributes"] is None
    response = client.post(
        "/api/ministryrequest/910/pageflag/redline",
        json={"documentids": [910001]},
        headers={"Authorization": "Bearer " + identity.token()},
    )
    assert response.status_code == 200
    assert json.loads(response.get_data(as_text=True)) == rows


@pytest.mark.parametrize(
    "offset,expected",
    [(None, "2026-01-02T03:04:05+00:00"), (-8, "2026-01-02T11:04:05+00:00")],
)
def test_inferred_model_dates_preserve_baseline_utc_format(offset, expected):
    from datetime import datetime, timezone, timedelta
    from reviewer_api.models.DocumentPageflags import DocumentPageflagSchema

    value = datetime(
        2026,
        1,
        2,
        3,
        4,
        5,
        tzinfo=None if offset is None else timezone(timedelta(hours=offset)),
    )
    result = DocumentPageflagSchema().dump({"created_at": value, "updated_at": None})
    assert result["created_at"] == expected
    assert result["updated_at"] is None
