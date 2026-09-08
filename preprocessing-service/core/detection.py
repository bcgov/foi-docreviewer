"""Shared result type returned by every detector's standalone restore_pdf."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RestoreResult:
    """Outcome of a single detector's restoration run."""

    hidden_found: bool
    spans_restored: int
    pages_affected: int
    wrote_output: bool
