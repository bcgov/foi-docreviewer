from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

import pytest

from reviewer_api.models.Annotations import Annotation
from reviewer_api.services.annotationservice import annotationservice


def _query_chain():
    query = Mock()
    query.select_from.return_value = query
    query.join.return_value = query
    query.filter.return_value = query
    query.group_by.return_value = query
    query.order_by.return_value = query
    query.subquery.return_value = SimpleNamespace(
        c=SimpleNamespace(
            documentmasterid=object(),
            processingparentid=object(),
        )
    )
    return query


def _session_with_paginate(paginate):
    deleted_exists = MagicMock()
    deleted_exists.correlate.return_value = deleted_exists

    deleted_query = _query_chain()
    deleted_query.exists.return_value = deleted_exists

    original_query = _query_chain()
    replaced_no_conversion_query = _query_chain()
    replaced_other_query = _query_chain()

    annotation_query = _query_chain()
    annotation_query.paginate = paginate

    session = Mock()
    session.query.side_effect = [
        deleted_query,
        original_query,
        replaced_no_conversion_query,
        replaced_other_query,
        annotation_query,
    ]
    return session, annotation_query


def test_get_request_annotations_pagination_closes_session_after_paginating():
    expected = SimpleNamespace(items=[])
    session, annotation_query = _session_with_paginate(Mock(return_value=expected))

    with patch("reviewer_api.models.Annotations.db.session", session):
        result = Annotation.get_request_annotations_pagination(627, [3], 1, 3500)

    assert result is expected
    annotation_query.paginate.assert_called_once_with(
        page=1,
        per_page=3500,
    )
    session.close.assert_called_once()


def test_get_request_annotations_pagination_closes_session_when_paginate_fails():
    paginate = Mock(side_effect=RuntimeError("database error"))
    session, _annotation_query = _session_with_paginate(paginate)

    with patch("reviewer_api.models.Annotations.db.session", session):
        with pytest.raises(RuntimeError, match="database error"):
            Annotation.get_request_annotations_pagination(627, [3], 1, 3500)

    session.close.assert_called_once()


def test_getrequestannotationspagination_formats_model_result():
    result = SimpleNamespace(
        page=1,
        pages=1,
        total=1,
        prev_num=None,
        next_num=None,
        has_next=False,
        has_prev=False,
        items=[
            SimpleNamespace(
                documentid=101,
                annotation='<redact page="1" />',
            )
        ],
    )

    with patch(
        "reviewer_api.services.annotationservice.Annotation.get_request_annotations_pagination",
        return_value=result,
    ) as get_page:
        response = annotationservice().getrequestannotationspagination(
            ministryrequestid=627,
            mappedlayerids=[3],
            page=1,
            size=3500,
        )

    get_page.assert_called_once_with(627, [3], 1, 3500)
    assert response["meta"]["page"] == 1
    assert 101 in response["data"]
