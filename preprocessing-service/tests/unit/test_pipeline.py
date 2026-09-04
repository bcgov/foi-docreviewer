"""Unit tests for core.pipeline -- no Docker, no network."""

from pathlib import Path

import pymupdf

import core.pipeline as pipeline
from core.pipeline import run_pipeline


def _make_pdf(path: Path, pages: int) -> None:
    doc = pymupdf.open()
    for _ in range(pages):
        doc.new_page(width=200, height=200)
    doc.save(path)
    doc.close()


def test_detectors_run_in_order_and_aggregate_results(tmp_path, monkeypatch):
    src = tmp_path / "in.pdf"
    dst = tmp_path / "out.pdf"
    _make_pdf(src, pages=2)
    calls = []

    def detector_a(page):
        calls.append((page.number, "a"))
        return 1 if page.number == 0 else 0

    def detector_b(page):
        calls.append((page.number, "b"))
        return 2

    monkeypatch.setattr(pipeline, "DETECTORS", [("a", detector_a), ("b", detector_b)])

    result = run_pipeline(src, dst)

    assert calls == [(0, "a"), (0, "b"), (1, "a"), (1, "b")]
    assert result.spans_restored == 5
    assert result.pages_affected == 2
    assert result.detectors["a"].pages_affected == 1
    assert result.detectors["b"].pages_affected == 2
    assert result.wrote_output is True
    assert dst.exists()


def test_clean_pdf_writes_no_output(tmp_path, monkeypatch):
    src = tmp_path / "in.pdf"
    dst = tmp_path / "out.pdf"
    _make_pdf(src, pages=1)
    monkeypatch.setattr(pipeline, "DETECTORS", [("noop", lambda page: 0)])

    result = run_pipeline(src, dst)

    assert result.hidden_found is False
    assert result.spans_restored == 0
    assert result.pages_affected == 0
    assert result.wrote_output is False
    assert not dst.exists()
    assert result.detectors["noop"].hidden_found is False
