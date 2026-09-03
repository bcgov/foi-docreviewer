"""Unit tests for core.hidden_text -- no Docker, no network."""

import pymupdf
import pytest

from core.hidden_text import restore_pdf


def _make_pdf(path, *, clip: bool):
    """A one-page PDF with a line of text. When clip=True the text is wrapped
    in a path clip that excludes it (a redaction-by-clipping)."""
    doc = pymupdf.open()
    page = doc.new_page(width=300, height=200)
    page.insert_text((20, 100), "TOP_SECRET_LEAK", fontsize=13)
    if clip:
        xref = page.get_contents()[0]
        body = doc.xref_stream(xref)
        # Path clip (m/l/h W n) to a strip well above the text baseline.
        wrapped = b"q\n0 180 m 300 180 l 300 200 l 0 200 l h\nW\nn\n" + body + b"\nQ\n"
        doc.update_stream(xref, wrapped)
    doc.save(path)
    doc.close()


def test_clipped_text_is_restored(tmp_path):
    src = tmp_path / "in.pdf"
    dst = tmp_path / "out.pdf"
    _make_pdf(src, clip=True)

    # Sanity: the text is genuinely hidden in the source.
    assert "TOP_SECRET_LEAK" not in pymupdf.open(src)[0].get_text()

    result = restore_pdf(src, dst)

    assert result.hidden_found is True
    assert result.spans_restored == 1
    assert result.pages_affected == 1
    assert result.wrote_output is True
    assert dst.exists()
    assert "TOP_SECRET_LEAK" in pymupdf.open(dst)[0].get_text()


def test_clean_pdf_produces_no_output(tmp_path):
    src = tmp_path / "in.pdf"
    dst = tmp_path / "out.pdf"
    _make_pdf(src, clip=False)

    result = restore_pdf(src, dst)

    assert result.hidden_found is False
    assert result.spans_restored == 0
    assert result.wrote_output is False
    assert not dst.exists()


def test_unmapped_glyphs_are_not_reported_as_hidden(tmp_path):
    """A '�'-only span is a decoding artifact, not a redaction."""
    src = tmp_path / "in.pdf"
    dst = tmp_path / "out.pdf"
    doc = pymupdf.open()
    doc.new_page(width=200, height=200)
    doc.save(src)
    doc.close()

    result = restore_pdf(src, dst)
    assert result.spans_restored == 0


def test_missing_file_raises(tmp_path):
    with pytest.raises(Exception):
        restore_pdf(tmp_path / "nope.pdf", tmp_path / "out.pdf")
