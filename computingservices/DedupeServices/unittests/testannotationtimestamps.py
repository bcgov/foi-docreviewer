"""Exercise the live annotation formatter and generated comment-summary PDF."""

import os
import sys
import time
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from PyPDF2 import PdfReader, PdfWriter
from PyPDF2.generic import ArrayObject, DictionaryObject, FloatObject, NameObject, TextStringObject


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Configuration normally fetches upload formats at import time. Keep the test
# fully local; PDF/date dependencies and the actual service remain real.
formats = Mock()
formats.json.return_value = {"conversion": [".msg"], "dedupe": [], "nonredactable": []}
with patch("requests.request", return_value=formats):
    from services import s3documentservice


@pytest.fixture(params=["UTC", "America/Vancouver", "America/Los_Angeles"])
def worker_timezone(request):
    original = os.environ.get("TZ")
    os.environ["TZ"] = request.param
    if hasattr(time, "tzset"):
        time.tzset()
    yield
    if original is None:
        os.environ.pop("TZ", None)
    else:
        os.environ["TZ"] = original
    if hasattr(time, "tzset"):
        time.tzset()


@pytest.mark.parametrize("source,expected", [
    ("D:20250115200000Z", "2025/01/15 12:00:00 PM Pacific Time"),
    ("D:20260115200000Z", "2026/01/15 12:00:00 PM Pacific Time"),
    ("D:20260308095959Z", "2026/03/08 01:59:59 AM Pacific Time"),
    ("D:20260308100000Z", "2026/03/08 03:00:00 AM Pacific Time"),
    ("D:20261101085959Z", "2026/11/01 01:59:59 AM Pacific Time"),
    ("D:20261101090000Z", "2026/11/01 02:00:00 AM Pacific Time"),
    ("D:20261103073000Z", "2026/11/03 12:30:00 AM Pacific Time"),
    ("D:20261102233100Z", "2026/11/02 04:31:00 PM Pacific Time"),
    ("D:20270115190000Z", "2027/01/15 12:00:00 PM Pacific Time"),
])
def test_annotation_preserves_vancouver_history_and_no_fall_back(worker_timezone, source, expected):
    assert s3documentservice.__converttoPST(source) == expected


@pytest.mark.parametrize("source", [
    "D:20261103003000-07'00'",
    "D:20261103033000-0400",
    "D:20261103130000+05'30'",
    "D:20261103003000-07",
    "D:20261103073000Z00'00'",
])
def test_annotation_honours_source_offset(worker_timezone, source):
    assert s3documentservice.__converttoPST(source) == "2026/11/03 12:30:00 AM Pacific Time"


def test_annotation_preserves_legacy_utc_naive_contract(worker_timezone):
    # reviewer_api/services/annotationservice.py normalizes its saved XFDF
    # creationdate/date to UTC and serializes D:YYYYMMDDHHmmSS without a suffix.
    assert s3documentservice.__converttoPST("D:20261103073000") == "2026/11/03 12:30:00 AM Pacific Time"


@pytest.mark.parametrize("source", [
    None, "", "not a PDF date", "D:2026",
    "D:20260230073000Z", "D:20261103073000+2500", "D:20261103073000+1260",
    "D:18990101000000Z", "D:20261103073000Z trailing text",
])
def test_annotation_keeps_unknown_dates_explicit(worker_timezone, source):
    assert s3documentservice.__converttoPST(source) == "Unknown"


@pytest.mark.parametrize("source,expected", [
    ("D:20261103033000-04'00'", "2026/11/03 12:30:00 AM Pacific Time"),
    ("D:20250115200000Z", "2025/01/15 12:00:00 PM Pacific Time"),
    ("D:20261103073000", "2026/11/03 12:30:00 AM Pacific Time"),
    ("D:invalid", "Unknown"),
])
def test_generated_comment_summary_contains_converted_timestamp(worker_timezone, source, expected):
    original = PdfWriter()
    original.add_blank_page(width=612, height=792)
    annotation = DictionaryObject({
        NameObject("/Type"): NameObject("/Annot"),
        NameObject("/Subtype"): NameObject("/Text"),
        NameObject("/Rect"): ArrayObject([FloatObject(n) for n in [40, 40, 60, 60]]),
        NameObject("/Contents"): TextStringObject("Synthetic timezone fixture"),
        NameObject("/T"): TextStringObject("QA"),
        NameObject("/Subj"): TextStringObject("Note"),
        NameObject("/CreationDate"): TextStringObject(source),
    })
    original.pages[0][NameObject("/Annots")] = ArrayObject([original._add_object(annotation)])
    original_bytes = BytesIO()
    original.write(original_bytes)
    original_bytes.seek(0)
    reader = PdfReader(original_bytes)
    pagecount, rendered = s3documentservice.createpagesforcomments(
        reader.pages[0], 0, PdfWriter(), reader, 1, "timezone-fixture.pdf")
    assert pagecount == 2
    output = BytesIO()
    rendered.write(output)
    output.seek(0)
    summary = PdfReader(output).pages[1].extract_text()
    assert expected in summary
    assert " PST" not in summary
    assert "Synthetic timezone fixture" in summary
