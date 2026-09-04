"""Run registered PDF detectors over each page in one document pass."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

from core.clip_hidden_text import restore_page as clip_hidden_text_restore_page
from core.detection import RestoreResult

DETECTORS: list[tuple[str, Callable[[pymupdf.Page], int]]] = [
    ("clip_hidden_text", clip_hidden_text_restore_page),
]


@dataclass
class PipelineResult:
    """Combined outcome of all registered detector runs."""

    hidden_found: bool
    spans_restored: int
    pages_affected: int
    wrote_output: bool
    detectors: dict[str, RestoreResult] = field(default_factory=dict)


def run_pipeline(src: str | Path, dst: str | Path) -> PipelineResult:
    """Run every registered detector over `src` and save detected changes."""
    src, dst = Path(src), Path(dst)
    doc = pymupdf.open(src)
    detector_spans = dict.fromkeys((name for name, _ in DETECTORS), 0)
    detector_pages = dict.fromkeys((name for name, _ in DETECTORS), 0)
    touched_pages: set[int] = set()

    try:
        for page in doc:
            rotation = page.rotation
            if rotation:
                page.set_rotation(0)

            for name, detector in DETECTORS:
                spans = detector(page)
                if spans:
                    detector_spans[name] += spans
                    detector_pages[name] += 1
                    touched_pages.add(page.number)

            if rotation:
                page.set_rotation(rotation)

        spans_restored = sum(detector_spans.values())
        wrote_output = spans_restored > 0
        if wrote_output:
            dst.parent.mkdir(parents=True, exist_ok=True)
            doc.save(dst, garbage=4, deflate=True)

        detectors = {
            name: RestoreResult(
                hidden_found=detector_spans[name] > 0,
                spans_restored=detector_spans[name],
                pages_affected=detector_pages[name],
                wrote_output=wrote_output,
            )
            for name, _ in DETECTORS
        }
        return PipelineResult(
            hidden_found=spans_restored > 0,
            spans_restored=spans_restored,
            pages_affected=len(touched_pages),
            wrote_output=wrote_output,
            detectors=detectors,
        )
    finally:
        doc.close()
