from types import SimpleNamespace
from unittest.mock import Mock, patch

from reviewer_api.services.annotationservice import annotationservice


def test_getrequestannotationspagination_closes_session_after_formatting():
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

    close_session = Mock()

    with patch(
        "reviewer_api.services.annotationservice.Annotation.get_request_annotations_pagination",
        return_value=result,
    ) as get_page, patch(
        "reviewer_api.services.annotationservice.db.session.close",
        close_session,
    ):
        response = annotationservice().getrequestannotationspagination(
            ministryrequestid=627,
            mappedlayerids=[3],
            page=1,
            size=3500,
        )

    get_page.assert_called_once_with(627, [3], 1, 3500)
    close_session.assert_called_once()
    assert response["meta"]["page"] == 1
    assert 101 in response["data"]


def test_getrequestannotationspagination_closes_session_when_formatting_fails():
    result = SimpleNamespace(
        page=1,
        pages=1,
        total=1,
        prev_num=None,
        next_num=None,
        has_next=False,
        has_prev=False,
        items=[SimpleNamespace(documentid=101)],
    )

    close_session = Mock()

    with patch(
        "reviewer_api.services.annotationservice.Annotation.get_request_annotations_pagination",
        return_value=result,
    ), patch(
        "reviewer_api.services.annotationservice.db.session.close",
        close_session,
    ):
        try:
            annotationservice().getrequestannotationspagination(627, [3], 1, 3500)
        except AttributeError:
            pass
        else:
            raise AssertionError("Expected formatting to fail")

    close_session.assert_called_once()
