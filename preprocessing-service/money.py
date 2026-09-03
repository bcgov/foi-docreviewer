# money.py
"""
Money handling for the template.

Amounts are integer minor units everywhere: 1000 means 10.00. Integers are
exact, they serialise to JSON as themselves, and they cross a stream into a
consumer written in any other language without a precision conversation.
Floats cannot represent money exactly and are never used here.

This module is the only place a cents value becomes a human-readable string.
Payload models carry ints; formatting happens at output edges — log lines and
CLI output — so the wire format never depends on presentation.
"""


def format_cents(cents: int) -> str:
    """Render integer minor units for humans: 1350 -> '13.50'."""
    sign = "-" if cents < 0 else ""
    whole, fraction = divmod(abs(cents), 100)
    return f"{sign}{whole}.{fraction:02d}"
