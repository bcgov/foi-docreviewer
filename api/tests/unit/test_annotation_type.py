import inspect

from reviewer_api.models import AnnotationSections
from reviewer_api.models.Annotations import Annotation, get_annotation_type


def test_get_annotation_type_returns_root_tag_name():
    assert get_annotation_type('<redact page="1" />') == "redact"
    assert get_annotation_type('  <freetext><contents>x</contents></freetext>') == "freetext"
    assert get_annotation_type('<?xml version="1.0"?><highlight />') == "highlight"


def test_get_annotation_type_returns_none_for_empty_or_invalid_xml():
    assert get_annotation_type("") is None
    assert get_annotation_type(None) is None
    assert get_annotation_type("not xml") is None
