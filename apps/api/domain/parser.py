"""Deterministic parser for text-based MFCentral CAMS/KFintech CAS PDFs.

V1 intentionally rejects image-only and unfamiliar statement layouts instead of
inventing financial records.  Each parsed item retains its one-based PDF page.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
import re
from typing import Optional

MONEY = r"(?:₹|Rs\.?\s*)?([\d,]+(?:\.\d{1,4})?)"
DATE = r"(\d{2}[/-]\d{2}[/-]\d{4})"

@dataclass
class FundHolding:
    amc: str; folio: str; scheme_name: str; isin: Optional[str]
    opening_units: Optional[Decimal]; closing_units: Optional[Decimal]
    nav: Optional[Decimal]; valuation: Optional[Decimal]
    valuation_date: Optional[str]; source_page: int
    asset_class: Optional[str] = None
    invested_amount: Optional[Decimal] = None
    unrealised_pl: Optional[Decimal] = None
    unrealised_pl_pct: Optional[Decimal] = None

@dataclass
class Transaction:
    amc: str; folio: str; scheme_name: str; isin: Optional[str]
    date: Optional[str]; transaction_type: str; description: str
    amount: Optional[Decimal]; units: Optional[Decimal]; nav: Optional[Decimal]
    unit_balance: Optional[Decimal]; source_page: int

@dataclass
class ParseResult:
    holdings: list[FundHolding]; transactions: list[Transaction]
    pages: dict[int, str]; warnings: list[str]

def decimal(value: str | None) -> Optional[Decimal]:
    if not value: return None
    try:
        cleaned = value.replace("₹", "").replace("Rs.", "").replace(",", "").strip()
        if cleaned.startswith("(") and cleaned.endswith(")"): cleaned = "-" + cleaned[1:-1]
        return Decimal(cleaned)
    except Exception: return None

def normalize_transaction(description: str) -> str:
    text = description.lower()
    if "payment not received" in text or "payment failed" in text or "failed" in text: return "FAILED_PAYMENT"
    if "sip cancelled" in text or "sip canceled" in text: return "SIP_CANCELLED"
    if "sipregistered" in text or "sip registered" in text: return "SIP_REGISTERED"
    if "address updated" in text: return "ADDRESS_UPDATE"
    if any(x in text for x in ("systematic purchase", "purchase - systematic", "sys. investment", "sip")): return "SIP_PURCHASE"
    if "redemption" in text or "switch out" in text: return "REDEMPTION"
    if "purchase" in text or "switch in" in text: return "PURCHASE"
    return "OTHER"

def _first(pattern: str, text: str, flags=re.I) -> Optional[str]:
    m = re.search(pattern, text, flags); return m.group(1).strip() if m else None

def parse_page_text(text: str, page: int, amc: str = "unknown") -> tuple[list[FundHolding], list[Transaction]]:
    """Parse a page/section. Exposed for repeatable tests and format iteration."""
    folio = _first(r"(?:Folio(?:\s*(?:No|Number))?\s*[:#-]?\s*)([A-Za-z0-9/-]+)", text) or "unknown"
    isin = _first(r"\b(ISIN\s*[:#-]?\s*)?((?:INF|INE)[A-Z0-9]{9,10})\b", text)
    if isin and isin.upper().startswith("ISIN"): isin = _first(r"\b((?:INF|INE)[A-Z0-9]{9,10})\b", text)
    scheme = _first(r"(?:Scheme(?:\s+Name)?|Fund)\s*[:#-]?\s*([^\n]+)", text)
    # MFCentral commonly prints the scheme immediately before an ISIN.
    if not scheme and isin:
        before = text[:text.find(isin)].strip().splitlines()
        scheme = before[-1].strip() if before else None
    if not scheme: return [], []
    opening = decimal(_first(r"Opening(?:\s+Unit(?:s)?(?:\s+Balance)?)?\s*[:]?\s*([\d,.]+)", text))
    closing = decimal(_first(r"Closing(?:\s+Unit(?:s)?(?:\s+Balance)?)?\s*[:]?\s*([\d,.]+)", text))
    nav = decimal(_first(r"(?:NAV|NAV/Price)\s*(?:as on [^\n:]*)?[:]?\s*([\d,.]+)", text))
    value = decimal(_first(r"(?:Valuation|Market Value|Current Value)\s*[:]?\s*(?:₹|Rs\.?\s*)?([\d,.]+)", text))
    valuation_date = _first(r"(?:Valuation|NAV).*?(\d{2}[/-]\d{2}[/-]\d{4})", text)
    holdings = [FundHolding(amc, folio, scheme, isin, opening, closing, nav, value, valuation_date, page)] if closing is not None or value is not None else []
    transactions = []
    # A conservative row form: date, free-text description, amount, units, NAV, running balance.
    row = re.compile(DATE + r"\s+(.+?)\s+([\d,]+\.\d{1,2})\s+(-?[\d,]+\.\d{1,4})\s+([\d,]+\.\d{1,4})\s+(-?[\d,]+\.\d{1,4})(?:\s|$)")
    for m in row.finditer(text):
        desc = m.group(2).strip()
        transactions.append(Transaction(amc, folio, scheme, isin, m.group(1), normalize_transaction(desc), desc, decimal(m.group(3)), decimal(m.group(4)), decimal(m.group(5)), decimal(m.group(6)), page))
    # Preserve important non-financial / failed events even when their table columns are absent.
    for line in text.splitlines():
        kind = normalize_transaction(line)
        if kind in {"FAILED_PAYMENT", "SIP_CANCELLED", "SIP_REGISTERED", "ADDRESS_UPDATE"} and not any(t.description == line.strip() for t in transactions):
            transactions.append(Transaction(amc, folio, scheme, isin, _first(DATE, line), kind, line.strip(), None, None, None, None, page))
    return holdings, transactions

def parse_cas(path: str | Path) -> ParseResult:
    try: import pymupdf
    except ImportError as exc: raise RuntimeError("PyMuPDF is required; install requirements.txt") from exc
    source = Path(path)
    if not source.exists(): raise FileNotFoundError(source)
    doc = pymupdf.open(source); pages = {}; holdings = []; transactions = []; warnings = []
    current_amc = "unknown"; current = None
    date_row = re.compile(r"^\d{2}-[A-Z]{3}-\d{4}$")

    def save_transaction(day, segment, page):
        if not current or not segment: return
        numeric = [decimal(x) for x in segment if re.fullmatch(r"\(?[\d,]+(?:\.\d+)?\)?", x)]
        text = [x for x in segment if not re.fullmatch(r"\(?[\d,]+(?:\.\d+)?\)?", x)]
        if len(numeric) < 4 or not text: return
        # Failed-payment rows put the instalment number before amount; final four
        # columns remain amount, units, price, and running unit balance.
        amount, units, nav, balance = numeric[-4:]
        description = " ".join(text)
        transactions.append(Transaction(current["amc"], current["folio"], current["scheme_name"], current["isin"], day, normalize_transaction(description), description, amount, units, nav, balance, page))

    for index, pdf_page in enumerate(doc, 1):
        text = pdf_page.get_text("text").strip(); pages[index] = text
        if not text:
            warnings.append(f"Page {index} has no extractable text (image-only pages are unsupported in V1).")
            continue
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        pos = 0
        while pos < len(lines):
            line = lines[pos]
            if line.endswith("Mutual Fund") and not line.startswith("Consolidated"):
                current_amc = line; pos += 1; continue
            folio = _first(r"FOLIO NO:\s*([^\s]+)", line)
            if folio:
                current = {"amc": current_amc, "folio": folio, "scheme_name": "unknown", "isin": None, "opening_units": None}
                pos += 1; continue
            if "ISIN:" in line and current:
                current["scheme_name"] = line.split("ISIN:", 1)[0].split("(Advisor:", 1)[0].strip()
                current["isin"] = _first(r"ISIN:\s*([A-Z0-9]+)", line)
                pos += 1; continue
            opening = _first(r"Opening Unit Balance:\s*([\d,.]+)", line)
            if opening and current: current["opening_units"] = decimal(opening)
            closing = _first(r"Closing Unit Balance:\s*([\d,.]+)", line)
            if closing and current:
                nav = decimal(_first(r"Nav as on .*?INR\s*([\d,.]+)", "\n".join(lines[pos:pos+3])))
                valuation = decimal(_first(r"Valuation on .*?: INR\s*([\d,.]+)", "\n".join(lines[pos:pos+4])))
                val_date = _first(r"Valuation on\s*(\d{2}-[A-Za-z]{3}-\d{4})", "\n".join(lines[pos:pos+4]))
                holdings.append(FundHolding(current["amc"], current["folio"], current["scheme_name"], current["isin"], current["opening_units"], decimal(closing), nav, valuation, val_date, index))
            if date_row.match(line):
                day = line; end = pos + 1
                while end < len(lines) and not date_row.match(lines[end]) and not lines[end].startswith(("Closing Unit Balance:", "FOLIO NO:")) and "ISIN:" not in lines[end]: end += 1
                save_transaction(day, lines[pos + 1:end], index)
                pos = end; continue
            pos += 1
    # Statements can repeat the last row of a page at the next-page header.
    unique = {}
    for txn in transactions:
        unique[(txn.amc, txn.folio, txn.scheme_name, txn.date, txn.description, txn.amount, txn.units, txn.nav, txn.unit_balance)] = txn
    transactions = list(unique.values())
    if not holdings: warnings.append("Unsupported CAS format or no holdings confidently parsed.")
    return ParseResult(holdings, transactions, pages, warnings)
