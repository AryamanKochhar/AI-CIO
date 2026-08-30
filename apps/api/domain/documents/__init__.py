"""Shared helpers for financial document adapters."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Optional


def parse_indian_decimal(value: str | None) -> Optional[Decimal]:
    """Parse Indian-formatted money/units like 1,45,971.00 or (98.75)."""
    if value is None:
        return None
    text = str(value).strip()
    if not text or text in {"--", "-", "—", "Nil", "nil", "N/A"}:
        return None
    text = (
        text.replace("₹", "")
        .replace("`", "")
        .replace("Rs.", "")
        .replace("INR", "")
        .replace(",", "")
        .replace(" ", "")
    )
    if text.startswith("(") and text.endswith(")"):
        text = "-" + text[1:-1]
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def looks_like_isin(token: str) -> bool:
    t = token.strip().upper()
    return len(t) == 12 and t.startswith(("INE", "INF")) and t.isalnum()
