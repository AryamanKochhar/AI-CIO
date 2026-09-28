"""Scrape public Indian bank FD interest-rate comparison tables.

Primary source: BankBazaar FD rates page.
Falls back to last DB snapshot, then a dated educational fallback table.
Not investment advice — rates change; verify with the bank before acting.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from typing import Any

import httpx
from sqlalchemy.orm import Session

from ai_cio.db.models import FdRateSnapshot

logger = logging.getLogger(__name__)

BANKBAZAAR_FD_URL = "https://www.bankbazaar.com/fixed-deposit-rate.html"
USER_AGENT = (
    "Mozilla/5.0 (compatible; AI-CIO/1.0; +https://localhost; educational FD rate research)"
)

# Educational fallback if live scrape + cache both unavailable (as-of note embedded).
_FALLBACK_RATES: list[dict[str, Any]] = [
    {"bank": "State Bank of India", "general_min": "3.05", "general_max": "6.45", "senior_min": "3.55", "senior_max": "7.05"},
    {"bank": "HDFC Bank", "general_min": "2.75", "general_max": "6.50", "senior_min": "3.25", "senior_max": "7.00"},
    {"bank": "ICICI Bank", "general_min": "2.75", "general_max": "6.50", "senior_min": "3.25", "senior_max": "7.10"},
    {"bank": "Axis Bank", "general_min": "3.00", "general_max": "6.45", "senior_min": "3.50", "senior_max": "7.20"},
    {"bank": "Kotak Mahindra Bank", "general_min": "2.75", "general_max": "6.70", "senior_min": "3.25", "senior_max": "7.20"},
    {"bank": "Bank of Baroda", "general_min": "3.50", "general_max": "6.45", "senior_min": "4.00", "senior_max": "7.00"},
    {"bank": "Punjab National Bank", "general_min": "3.00", "general_max": "6.60", "senior_min": "3.50", "senior_max": "7.10"},
    {"bank": "IDFC FIRST Bank", "general_min": "3.50", "general_max": "7.40", "senior_min": "4.00", "senior_max": "7.90"},
    {"bank": "IndusInd Bank", "general_min": "3.25", "general_max": "7.00", "senior_min": "3.75", "senior_max": "7.50"},
    {"bank": "YES Bank", "general_min": "3.25", "general_max": "7.00", "senior_min": "3.75", "senior_max": "7.75"},
]


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tables: list[list[list[str]]] = []
        self._in_table = False
        self._in_row = False
        self._in_cell = False
        self._current_table: list[list[str]] = []
        self._current_row: list[str] = []
        self._cell_buf = ""

    def handle_starttag(self, tag: str, attrs) -> None:
        t = tag.lower()
        if t == "table":
            self._in_table = True
            self._current_table = []
        elif self._in_table and t == "tr":
            self._in_row = True
            self._current_row = []
        elif self._in_row and t in {"td", "th"}:
            self._in_cell = True
            self._cell_buf = ""

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if t in {"td", "th"} and self._in_cell:
            self._in_cell = False
            text = re.sub(r"\s+", " ", self._cell_buf).strip()
            self._current_row.append(text)
        elif t == "tr" and self._in_row:
            self._in_row = False
            if self._current_row:
                self._current_table.append(self._current_row)
        elif t == "table" and self._in_table:
            self._in_table = False
            if self._current_table:
                self.tables.append(self._current_table)

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._cell_buf += data


_RATE_RE = re.compile(
    r"(?P<lo>\d+(?:\.\d+)?)\s*%?\s*(?:-|–|to)\s*(?P<hi>\d+(?:\.\d+)?)\s*%?",
    re.I,
)
_SINGLE_RE = re.compile(r"(?P<v>\d+(?:\.\d+)?)\s*%")


def _parse_rate_range(text: str) -> tuple[str | None, str | None]:
    raw = (text or "").replace(",", " ").strip()
    m = _RATE_RE.search(raw)
    if m:
        return m.group("lo"), m.group("hi")
    m2 = _SINGLE_RE.search(raw)
    if m2:
        return m2.group("v"), m2.group("v")
    return None, None


def _looks_like_bank_header(row: list[str]) -> bool:
    joined = " ".join(row).lower()
    return "bank" in joined and ("interest" in joined or "rate" in joined or "senior" in joined)


def parse_fd_rate_tables(html: str) -> list[dict[str, Any]]:
    parser = _TableParser()
    parser.feed(html)
    banks: dict[str, dict[str, Any]] = {}
    for table in parser.tables:
        if not table:
            continue
        start = 1 if _looks_like_bank_header(table[0]) else 0
        for row in table[start:]:
            if len(row) < 2:
                continue
            bank = row[0].strip()
            if not bank or bank.lower() in {"bank", "name of bank"}:
                continue
            if "bank" not in bank.lower() and len(bank) < 4:
                continue
            g_min, g_max = _parse_rate_range(row[1] if len(row) > 1 else "")
            s_min, s_max = _parse_rate_range(row[2] if len(row) > 2 else "")
            if g_min is None and s_min is None:
                continue
            prev = banks.get(bank)
            entry = {
                "bank": bank,
                "general_min": g_min,
                "general_max": g_max,
                "senior_min": s_min,
                "senior_max": s_max,
            }
            # Prefer wider / higher general_max when multiple tables overlap
            if prev is None:
                banks[bank] = entry
            else:
                try:
                    if Decimal(g_max or "0") > Decimal(prev.get("general_max") or "0"):
                        banks[bank] = entry
                except (InvalidOperation, TypeError):
                    banks[bank] = entry
    return sorted(banks.values(), key=lambda r: r["bank"].lower())


def _extract_as_of(html: str) -> str | None:
    m = re.search(r"(?:as of|updated on|effective from)[^\n.<]{0,80}", html, re.I)
    if m:
        return re.sub(r"\s+", " ", m.group(0)).strip()[:240]
    return None


def scrape_bankbazaar_fd_rates(*, timeout: float = 20.0) -> dict[str, Any]:
    """Live scrape BankBazaar FD comparison page."""
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"}
    with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
        resp = client.get(BANKBAZAAR_FD_URL)
        resp.raise_for_status()
        html = resp.text
    rates = parse_fd_rate_tables(html)
    if not rates:
        raise ValueError("No FD rate rows parsed from BankBazaar HTML")
    return {
        "source": "bankbazaar",
        "source_url": BANKBAZAAR_FD_URL,
        "as_of_note": _extract_as_of(html),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "rates": rates,
        "status": "live",
    }


def get_fd_rates(
    db: Session | None = None,
    *,
    force_refresh: bool = False,
    max_age_hours: int = 24,
) -> dict[str, Any]:
    """Return FD rates: live scrape → recent DB snapshot → educational fallback."""
    if db is not None and not force_refresh:
        latest = (
            db.query(FdRateSnapshot)
            .filter(FdRateSnapshot.status == "ok")
            .order_by(FdRateSnapshot.fetched_at.desc())
            .first()
        )
        if latest is not None:
            age_h = (datetime.now(timezone.utc) - latest.fetched_at.replace(tzinfo=timezone.utc)).total_seconds() / 3600
            if age_h <= max_age_hours and (latest.payload or {}).get("rates"):
                return {
                    **latest.payload,
                    "status": "cached",
                    "snapshot_id": latest.id,
                    "fetched_at": latest.fetched_at.isoformat(),
                }

    try:
        payload = scrape_bankbazaar_fd_rates()
        if db is not None:
            row = FdRateSnapshot(
                source=payload["source"],
                source_url=payload["source_url"],
                as_of_note=payload.get("as_of_note"),
                payload={"rates": payload["rates"], "source": payload["source"], "source_url": payload["source_url"]},
                status="ok",
            )
            db.add(row)
            db.flush()
            payload["snapshot_id"] = row.id
        payload["disclaimer"] = (
            "Scraped public comparison rates for education. Confirm with the bank; not a product recommendation."
        )
        return payload
    except Exception as exc:
        logger.warning("fd_rate_scrape_failed err=%s", exc)
        if db is not None:
            latest = (
                db.query(FdRateSnapshot)
                .filter(FdRateSnapshot.status == "ok")
                .order_by(FdRateSnapshot.fetched_at.desc())
                .first()
            )
            if latest and (latest.payload or {}).get("rates"):
                out = dict(latest.payload)
                out.update(
                    {
                        "status": "stale_cache",
                        "snapshot_id": latest.id,
                        "fetched_at": latest.fetched_at.isoformat(),
                        "scrape_error": str(exc),
                        "disclaimer": "Using last cached scrape after live fetch failed. Confirm rates with the bank.",
                    }
                )
                return out
            db.add(
                FdRateSnapshot(
                    source="bankbazaar",
                    source_url=BANKBAZAAR_FD_URL,
                    payload={"rates": []},
                    status="error",
                    error=str(exc),
                )
            )
            db.flush()

        return {
            "source": "fallback_educational",
            "source_url": BANKBAZAAR_FD_URL,
            "as_of_note": "Educational fallback table (live scrape unavailable)",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "rates": list(_FALLBACK_RATES),
            "status": "fallback",
            "scrape_error": str(exc),
            "disclaimer": (
                "Live scrape unavailable — showing educational fallback rates. "
                "Verify current rates on the bank website before acting. Not investment advice."
            ),
        }


def match_bank_rate(bank_name: str, rates: list[dict[str, Any]]) -> dict[str, Any] | None:
    needle = re.sub(r"[^a-z0-9]", "", (bank_name or "").lower())
    if not needle:
        return None
    for row in rates:
        key = re.sub(r"[^a-z0-9]", "", (row.get("bank") or "").lower())
        if needle in key or key in needle:
            return row
    return None
