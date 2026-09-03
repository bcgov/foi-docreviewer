"""Shared helpers for building test PDFs."""

from __future__ import annotations

from pathlib import Path

import pymupdf

SECRET = "TOP_SECRET_LEAK"


def make_pdf(path: str | Path, *, clip: bool) -> Path:
    """One-page PDF with a line of text. clip=True wraps it in a path clip that
    excludes it (redaction-by-clipping)."""
    path = Path(path)
    doc = pymupdf.open()
    page = doc.new_page(width=300, height=200)
    page.insert_text((20, 100), SECRET, fontsize=13)
    if clip:
        xref = page.get_contents()[0]
        body = doc.xref_stream(xref)
        wrapped = b"q\n0 180 m 300 180 l 300 200 l 0 200 l h\nW\nn\n" + body + b"\nQ\n"
        doc.update_stream(xref, wrapped)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(path)
    doc.close()
    return path


def pdf_bytes(*, clip: bool) -> bytes:
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".pdf") as fh:
        make_pdf(fh.name, clip=clip)
        return Path(fh.name).read_bytes()
