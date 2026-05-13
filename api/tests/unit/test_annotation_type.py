import inspect

from reviewer_api.models import AnnotationSections
from reviewer_api.models.Annotations import (
    Annotation,
    _build_annotation_values,
    get_annotation_type,
)


def test_get_annotation_type_returns_root_tag_name():
    assert get_annotation_type('<redact page="1" />') == "redact"
    assert get_annotation_type('  <freetext><contents>x</contents></freetext>') == "freetext"
    assert get_annotation_type('<?xml version="1.0"?><highlight />') == "highlight"


def test_get_annotation_type_returns_none_for_empty_or_invalid_xml():
    assert get_annotation_type("") is None
    assert get_annotation_type(None) is None
    assert get_annotation_type("not xml") is None


def test_new_annotation_values_include_annotation_type():
    values = _build_annotation_values(
        {"name": "a1", "docid": 10, "xml": '<redact page="1" />', "page": 0},
        redactionlayerid=4,
        userinfo={"userid": "u"},
        version=1,
        documentversion=1,
    )

    assert values["annotationtype"] == "redact"


def test_bulk_annotation_values_include_annotation_type():
    values = _build_annotation_values(
        {"name": "a1", "docid": 10, "xml": '<redact page="1" />', "page": 0},
        redactionlayerid=4,
        userinfo={"userid": "u"},
        version=3,
        documentversion=1,
        annotationid=99,
    )

    assert values["annotationtype"] == "redact"
    assert values["version"] == 3
    assert values["annotationid"] == 99


def test_update_annotation_values_include_annotation_type():
    values = _build_annotation_values(
        {
            "name": "a1",
            "docid": 10,
            "docversion": 2,
            "xml": '<redact page="1" />',
            "page": 0,
        },
        redactionlayerid=4,
        userinfo={"userid": "u"},
        version=4,
        documentversion=2,
        annotationid=99,
    )

    assert values["annotationtype"] == "redact"
    assert values["documentversion"] == 2


def test_getredactionsbypage_filters_by_annotation_type():
    source = inspect.getsource(Annotation.getredactionsbypage)

    assert "Annotation.annotationtype == \"redact\"" in source
    assert "Annotation.annotation.ilike" not in source
    assert "%<redact %" not in source


def test_getredactionsbydocumentpages_filters_by_annotation_type():
    source = inspect.getsource(Annotation.getredactionsbydocumentpages)

    assert "Annotation.annotationtype == \"redact\"" in source
    assert "Annotation.annotation.ilike" not in source
    assert "%<redact %" not in source


def test_getredactedsectionsbyrequest_prefilters_by_annotation_type():
    source = inspect.getsource(AnnotationSections.AnnotationSection.getredactedsectionsbyrequest)

    assert "a.annotationtype = 'freetext'" in source
    assert "a.annotation LIKE '%%freetext%%'" not in source
    assert "a.annotation like '%%freetext%%'" not in source
