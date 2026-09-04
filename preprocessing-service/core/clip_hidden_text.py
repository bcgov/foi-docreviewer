"""Detect clip-hidden text in a PDF and re-draw it in place.

Detection principle: extract the page text twice, identically except that one
pass honors clip paths (TEXT_MEDIABOX_CLIP) and the other does not. A span that
appears only in the no-clip pass is text the renderer lays out but a clip stops
from being visible. Restoration re-draws each such span on top of the page, outside
every clip, in its own font / size / colour, so the text is visible.
"""

from __future__ import annotations

from pathlib import Path

import pymupdf

from core.detection import RestoreResult

pymupdf.TOOLS.mupdf_display_errors(False)

# The "dict" default flags minus TEXT_MEDIABOX_CLIP -- that bit is the only one
# that makes get_text honor clip paths. Every other bit (notably
# TEXT_CID_FOR_UNKNOWN_UNICODE) stays equal to the clipped pass so glyphs decode
# the same way and only genuinely clip-hidden spans show up as a difference.
_NOCLIP_FLAGS = pymupdf.TEXTFLAGS_DICT & ~pymupdf.TEXT_MEDIABOX_CLIP

# pymupdf span["flags"] bits and the Base-14 font code for each style combo.
_SPAN_MONO, _SPAN_ITALIC, _SPAN_SERIF, _SPAN_BOLD = 1, 2, 8, 16
_FONT_FAMILIES = {
    "mono": ("cour", "cobo", "coit", "cobi"),
    "serif": ("tiro", "tibo", "tiit", "tibi"),
    "sans": ("helv", "hebo", "heit", "hebi"),
}


def _is_junk(text: str) -> bool:
    """True if a span is only unmapped / undisplayable glyphs (eg. '�')."""
    return all(ch == "�" or not ch.isprintable() for ch in text)


def _base14(span: dict) -> str:
    """Closest built-in font to a span whose embedded (often subset) font
    insert_text cannot reuse."""
    f = span.get("flags", 0)
    if f & _SPAN_MONO:
        family = "mono"
    elif f & _SPAN_SERIF:
        family = "serif"
    else:
        family = "sans"
    idx = (1 if f & _SPAN_BOLD else 0) + (2 if f & _SPAN_ITALIC else 0)
    return _FONT_FAMILIES[family][idx]


def _hidden_spans(page: pymupdf.Page) -> list[dict]:
    """Spans present when clips are ignored but not when they are honored."""
    visible = set()
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                t = span["text"].strip()
                if t:
                    visible.add(
                        (round(span["bbox"][0], 1), round(span["bbox"][1], 1), t)
                    )

    hidden = []
    for block in page.get_text("dict", flags=_NOCLIP_FLAGS)["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                t = span["text"].strip()
                if not t or _is_junk(t):
                    continue
                key = (round(span["bbox"][0], 1), round(span["bbox"][1], 1), t)
                if key not in visible:
                    hidden.append(span)
    return hidden


def restore_page(page: pymupdf.Page) -> int:
    """Re-draw clip-hidden spans on `page` in place and return the count."""
    spans_restored = 0
    for s in _hidden_spans(page):
        origin = s.get("origin") or (s["bbox"][0], s["bbox"][3] - 1)
        try:
            color = pymupdf.sRGB_to_pdf(s.get("color", 0))
        except Exception:
            color = (0, 0, 0)
        try:
            page.insert_text(
                origin,
                s["text"],
                fontname=_base14(s),
                fontsize=s.get("size", 11),
                color=color,
            )
        except Exception:
            # Glyphs outside a Base-14 font, etc. -- skip that span.
            continue
        spans_restored += 1
    return spans_restored


def restore_pdf(src: str | Path, dst: str | Path) -> RestoreResult:
    """Re-draw clip-hidden text in `src` and save the result to `dst`.

    The output file is written only when hidden text is actually found.
    """
    src, dst = Path(src), Path(dst)
    doc = pymupdf.open(src)

    spans_restored = 0
    pages_affected = 0
    try:
        for page in doc:
            # Work in the page's unrotated coordinate space so get_text origins
            # and insert_text agree; restore the display rotation afterwards.
            rotation = page.rotation
            if rotation:
                page.set_rotation(0)

            page_hits = restore_page(page)

            if rotation:
                page.set_rotation(rotation)
            if page_hits:
                spans_restored += page_hits
                pages_affected += 1

        wrote_output = spans_restored > 0
        if wrote_output:
            dst.parent.mkdir(parents=True, exist_ok=True)
            doc.save(dst, garbage=4, deflate=True)

        return RestoreResult(
            hidden_found=spans_restored > 0,
            spans_restored=spans_restored,
            pages_affected=pages_affected,
            wrote_output=wrote_output,
        )
    finally:
        doc.close()
