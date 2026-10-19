"""CDSL Consolidated Account Statement classifier and parser.

Pure domain adapter — no database or HTTP imports.
Normalizes into structures compatible with the existing CAS persistence layer.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Optional

from domain.documents import looks_like_isin, parse_indian_decimal
from domain.parser import FundHolding, ParseResult, Transaction, decimal, normalize_transaction

PARSER_VERSION = "cdsl-cas-v1"

CDSL_MARKERS = (
    "Central Depository Services (India) Limited",
    "CONSOLIDATED ACCOUNT STATEMENT",
    "DEMAT ACCOUNTS HELD WITH CDSL",
    "MUTUAL FUND UNITS HELD WITH MF/RTA",
    "HOLDING STATEMENT AS ON",
    "CAS ID:",
)

DATE_DMY = re.compile(r"\b(\d{2}-\d{2}-\d{4})\b")
DATE_DMY_ALPHA = re.compile(
    r"\b(\d{2}-(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)-\d{4})\b",
    re.I,
)
PERIOD_FROM_TO = re.compile(
    r"PERIOD\s+FROM\s+(\d{2}-\d{2}-\d{4})\s+TO\s+(\d{2}-\d{2}-\d{4})",
    re.I,
)
PERIOD_STATEMENT = re.compile(
    r"Statement for the period from\s+(\d{2}-[A-Za-z]{3}-\d{4})\s+to\s+(\d{2}-[A-Za-z]{3}-\d{4})",
    re.I,
)
CAS_ID_RE = re.compile(r"CAS\s*ID\s*:\s*([A-Z0-9]+)", re.I)
BO_ID_RE = re.compile(r"BO\s*ID\s*:?\s*(\d{16})", re.I)
DP_ID_CLIENT_RE = re.compile(
    r"DP\s*Id\s*:\s*([A-Z0-9]+)\s+Client\s*Id\s*:?\s*([A-Z0-9]+)",
    re.I,
)
DP_NAME_RE = re.compile(r"DP\s*Name\s*:?\s*(.+)", re.I)
ISIN_LINE = re.compile(r"^(INE|INF)[A-Z0-9]{9}$")
MONEY_LINE = re.compile(r"^-?[\d,]+\.\d{1,4}$")
UNIT_LINE = re.compile(r"^-?[\d,]+\.\d{1,6}$|^--$")
MONTH_YEAR = re.compile(
    r"^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}$",
    re.I,
)


@dataclass
class DematAccount:
    depository: str
    dp_name: str
    dp_id: str | None = None
    client_id: str | None = None
    bo_id: str | None = None
    account_status: str | None = None
    holder_type: str | None = None
    value: Decimal | None = None
    isin_count: int | None = None


@dataclass
class PortfolioSnapshot:
    month_year: str
    valuation: Decimal
    change_amount: Decimal | None = None
    change_pct: Decimal | None = None


@dataclass
class AssetAllocation:
    asset_class: str
    value: Decimal
    percentage: Decimal | None = None


@dataclass
class CdslMetadata:
    cas_id: str | None = None
    statement_start: str | None = None
    statement_end: str | None = None
    holder_name: str | None = None
    pan_masked: bool = False
    total_portfolio_value: Decimal | None = None
    equity_value: Decimal | None = None
    mutual_fund_value: Decimal | None = None
    demat_accounts: list[DematAccount] = field(default_factory=list)
    snapshots: list[PortfolioSnapshot] = field(default_factory=list)
    allocation: list[AssetAllocation] = field(default_factory=list)
    successful_sections: list[str] = field(default_factory=list)
    failed_sections: list[str] = field(default_factory=list)
    status: str = "processed"  # processed | partial | failed


@dataclass
class CdslParseResult(ParseResult):
    metadata: CdslMetadata = field(default_factory=CdslMetadata)


def classify_cdsl_cas(pages: dict[int, str] | str) -> tuple[bool, list[str]]:
    """Return (is_cdsl_cas, matched_markers). Requires multiple markers."""
    if isinstance(pages, dict):
        text = "\n".join(pages.values())
    else:
        text = pages
    upper = text
    matched = [m for m in CDSL_MARKERS if m in upper]
    # Require core identity signals — not a single string.
    has_cdsl_org = "Central Depository Services (India) Limited" in text
    has_cas = "CONSOLIDATED ACCOUNT STATEMENT" in text
    has_section = any(
        s in text
        for s in (
            "DEMAT ACCOUNTS HELD WITH CDSL",
            "MUTUAL FUND UNITS HELD WITH MF/RTA",
            "HOLDING STATEMENT AS ON",
            "CAS ID:",
        )
    )
    return (has_cdsl_org and has_cas and has_section), matched


def normalize_demat_txn_type(description: str) -> str:
    text = description.upper()
    if "EP-DR" in text or "PAYOUT-DR" in text or "-DR" in text.split()[0:1]:
        return "DEBIT"
    if any(x in text for x in ("PAYOUT-CR", "INTDEP-CR", "-CR", "CREDIT")):
        return "CREDIT"
    if "DEBIT" in text or "DR " in text:
        return "DEBIT"
    return "OTHER"


def _lines(text: str) -> list[str]:
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def _extract_pages(path: Path) -> dict[int, str]:
    try:
        import pymupdf
    except ImportError as exc:
        raise RuntimeError("PyMuPDF is required; install requirements.txt") from exc
    try:
        # Parse bytes so malformed PDFs cannot leave a file handle locked on
        # Windows while the exception traceback remains alive.
        doc = pymupdf.open(stream=path.read_bytes(), filetype="pdf")
    except Exception as exc:
        raise ValueError(
            "This doesn't appear to be a valid CDSL Consolidated Account Statement PDF."
        ) from exc
    pages: dict[int, str] = {}
    with doc:
        for i in range(doc.page_count):
            pages[i + 1] = doc[i].get_text("text")
    if not pages:
        raise ValueError(
            "This doesn't appear to be a CDSL Consolidated Account Statement."
        )
    return pages


def _find_period(text: str) -> tuple[str | None, str | None]:
    m = PERIOD_FROM_TO.search(text)
    if m:
        return m.group(1), m.group(2)
    m = PERIOD_STATEMENT.search(text)
    if m:
        return m.group(1), m.group(2)
    # Fallback from page 1 header
    m = re.search(
        r"FOR THE PERIOD FROM\s+(\d{2}-\d{2}-\d{4})\s+TO\s+(\d{2}-\d{2}-\d{4})",
        text,
        re.I,
    )
    if m:
        return m.group(1), m.group(2)
    return None, None


def _mask_pan(text: str) -> bool:
    return bool(re.search(r"PAN\s*:?\s*[A-Z]{5}\d{4}[A-Z]", text, re.I))


def _parse_summary_values(text: str, meta: CdslMetadata) -> None:
    m = re.search(r"YOUR CONSOLIDATED\s+PORTFOLIO VALUE.*?`\s*([\d,]+\.\d{2})", text, re.S | re.I)
    if not m:
        m = re.search(r"Total Portfolio Value across investments\s+₹\s*([\d,]+\.\d{2})", text, re.I)
    if not m:
        m = re.search(r"Grand Total\s*\n\s*([\d,]+\.\d{2})", text, re.I)
    if m:
        meta.total_portfolio_value = parse_indian_decimal(m.group(1))

    # Prefer the asset-class block: "Asset Class / Value / Percentage"
    block = _section_between(
        text,
        ("Consolidated Portfolio for Accounts for the Month", "Assets Class"),
        ("DEMAT ACCOUNTS HELD WITH CDSL", "Account Details\nAccount Details"),
    )
    source = block or text
    seen: set[str] = set()
    for m in re.finditer(
        r"(Equity|Mutual Fund Folios)\s*\n\s*([\d,]+\.\d{2})\s*\n\s*([\d.]+)",
        source,
        re.I,
    ):
        key = "equity" if m.group(1).lower().startswith("equity") else "mutual_fund"
        if key in seen:
            continue
        seen.add(key)
        value = parse_indian_decimal(m.group(2)) or Decimal("0")
        pct = parse_indian_decimal(m.group(3))
        meta.allocation.append(AssetAllocation(asset_class=key, value=value, percentage=pct))
        if key == "equity":
            meta.equity_value = value
        else:
            meta.mutual_fund_value = value

    # Page-1 style: labels then three values in order CDSL, NSDL, MF
    if meta.mutual_fund_value is None:
        m = re.search(
            r"CDSL Demat Accounts\s*\nNSDL Demat Accounts\s*\nMutual Fund Folios\s*\n"
            r"([\d,]+\.\d{2})\s*\n([\d,]+\.\d{2})\s*\n([\d,]+\.\d{2})",
            text,
            re.I,
        )
        if m:
            meta.equity_value = parse_indian_decimal(m.group(1))
            meta.mutual_fund_value = parse_indian_decimal(m.group(3))


def _parse_accounts(text: str, meta: CdslMetadata) -> None:
    # Summary table style: CDSL Demat Account / DP / Dp Id / Client Id / count / value
    for m in re.finditer(
        r"(CDSL|NSDL)\s+Demat Account\s*\n([^\n]+)\s*\nDP Id:\s*([A-Z0-9]+)\s+Client Id\s*:?\s*([A-Z0-9]+)\s*\n(\d+)\s*\n([\d,]+\.\d{2})",
        text,
        re.I,
    ):
        meta.demat_accounts.append(
            DematAccount(
                depository=m.group(1).upper(),
                dp_name=m.group(2).strip(),
                dp_id=m.group(3).strip(),
                client_id=m.group(4).strip(),
                bo_id=(m.group(3) + m.group(4)) if m.group(1).upper() == "CDSL" else None,
                isin_count=int(m.group(5)),
                value=parse_indian_decimal(m.group(6)),
            )
        )

    # Detailed account pages
    if not meta.demat_accounts:
        current_dep = None
        for line in _lines(text):
            if "CDSL Demat Accounts" in line:
                current_dep = "CDSL"
            elif "NSDL Demat Accounts" in line:
                current_dep = "NSDL"
            dm = DP_NAME_RE.match(line)
            if dm and current_dep:
                name = dm.group(1).strip()
                meta.demat_accounts.append(
                    DematAccount(depository=current_dep, dp_name=name)
                )
            ids = re.search(r"DP\s*ID\s*:?\s*([A-Z0-9]+)\s+CLIENT\s*ID\s*:?\s*([A-Z0-9]+)", line, re.I)
            if ids and meta.demat_accounts:
                acc = meta.demat_accounts[-1]
                acc.dp_id = ids.group(1)
                acc.client_id = ids.group(2)
                if acc.depository == "CDSL" and acc.dp_id and acc.client_id:
                    acc.bo_id = acc.dp_id + acc.client_id
            if line.lower().startswith("account status") and meta.demat_accounts:
                meta.demat_accounts[-1].account_status = line.split(":", 1)[-1].strip()


def _parse_snapshots(text: str, meta: CdslMetadata) -> None:
    if "Consolidated Portfolio Valuation for Year" not in text:
        return
    # Slice the yearly valuation section
    start = text.find("Consolidated Portfolio Valuation for Year")
    end = text.find("Consolidated Portfolio for Accounts for the Month", start)
    section = text[start:end] if end > start else text[start:]
    lines = _lines(section)
    i = 0
    while i < len(lines):
        if MONTH_YEAR.match(lines[i]):
            month = lines[i]
            vals: list[Decimal] = []
            j = i + 1
            while j < len(lines) and len(vals) < 3:
                if MONTH_YEAR.match(lines[j]) or lines[j].startswith("माह"):
                    break
                d = parse_indian_decimal(lines[j])
                if d is not None and ("." in lines[j] or "," in lines[j]):
                    vals.append(d)
                j += 1
            if vals:
                meta.snapshots.append(
                    PortfolioSnapshot(
                        month_year=month,
                        valuation=vals[0],
                        change_amount=vals[1] if len(vals) > 1 else None,
                        change_pct=vals[2] if len(vals) > 2 else None,
                    )
                )
            i = j
            continue
        i += 1


def _section_between(text: str, start_markers: tuple[str, ...], end_markers: tuple[str, ...]) -> str:
    start = -1
    for m in start_markers:
        idx = text.find(m)
        if idx >= 0:
            start = idx
            break
    if start < 0:
        return ""
    end = len(text)
    for m in end_markers:
        idx = text.find(m, start + 1)
        if idx >= 0:
            end = min(end, idx)
    return text[start:end]


def _expand_holding_tokens(token: str) -> list[str]:
    parts: list[str] = []
    for part in re.split(r"\s+", token.strip()):
        if not part:
            continue
        if part == "--":
            parts.append("--")
        elif re.match(r"^--[\d,]+\.\d+$", part):
            parts.append("--")
            parts.append(part[2:])
        elif re.match(r"^-?[\d,]+\.\d+$", part) or part == "0" or part == "0.00":
            parts.append(part)
        else:
            parts.append(part)
    return parts


def _parse_equity_holdings(text: str, page_map: dict[int, str]) -> list[FundHolding]:
    holdings: list[FundHolding] = []
    folio = "CDSL"
    before = text[: text.find("HOLDING STATEMENT AS ON")] if "HOLDING STATEMENT AS ON" in text else text
    bos = list(BO_ID_RE.finditer(before))
    if bos:
        folio = bos[-1].group(1)

    for page, page_text in page_map.items():
        if "HOLDING STATEMENT AS ON" not in page_text and not any(
            looks_like_isin(ln) and ln.startswith("INE") for ln in _lines(page_text)
        ):
            continue
        if "HOLDING STATEMENT" not in page_text and "Value (`)" not in page_text and "Free Bal" not in page_text:
            # Only pages in holding section — require prior holding marker in document order
            if page < min((p for p, t in page_map.items() if "HOLDING STATEMENT AS ON" in t), default=999):
                continue
            if page > min((p for p, t in page_map.items() if "DEMAT ACCOUNTS HELD WITH NSDL" in t), default=999):
                continue

        as_on = _first(r"HOLDING STATEMENT AS ON\s+(\d{2}-\d{2}-\d{4})", page_text)
        lines = _lines(page_text)
        i = 0
        while i < len(lines):
            if looks_like_isin(lines[i]) and lines[i].startswith("INE"):
                isin = lines[i]
                name_parts: list[str] = []
                j = i + 1
                while j < len(lines) and not (
                    re.match(r"^-?[\d,]+\.\d+$", lines[j])
                    or lines[j] == "--"
                    or looks_like_isin(lines[j])
                    or lines[j].startswith("Portfolio Value")
                ):
                    if lines[j] in {"ISIN", "Security", "Current", "Bal", "Frozen", "Pledge", "Free Bal"}:
                        j += 1
                        continue
                    if re.search(r"[\u0900-\u097F]", lines[j]):
                        j += 1
                        continue
                    name_parts.append(lines[j])
                    j += 1

                tokens: list[str] = []
                while j < len(lines) and not looks_like_isin(lines[j]) and not lines[j].startswith("Portfolio Value"):
                    expanded = _expand_holding_tokens(lines[j])
                    if all(t == "--" or re.match(r"^-?[\d,]+\.\d+$", t) or t in {"0", "0.00"} for t in expanded):
                        tokens.extend(expanded)
                        j += 1
                        # Stop once we have a valuation candidate (comma or trailing 2-dp after price)
                        money_vals = [t for t in tokens if t != "--" and re.search(r"\d", t)]
                        if len(money_vals) >= 3 and (
                            "," in money_vals[-1] or re.search(r"\.\d{2}$", money_vals[-1])
                        ):
                            # Prefer stop when last looks like valuation (2 dp) and previous like price (4 dp)
                            if "," in money_vals[-1] or (
                                len(money_vals) >= 2
                                and re.search(r"\.\d{4}$", money_vals[-2])
                                and re.search(r"\.\d{2}$", money_vals[-1])
                            ):
                                break
                        continue
                    break

                money = [t for t in tokens if t != "--"]
                current = parse_indian_decimal(tokens[0]) if tokens and tokens[0] != "--" else (
                    Decimal("0") if tokens and tokens[0] == "--" else None
                )
                valuation = None
                nav = None
                if money:
                    # Valuation: prefer last token containing a thousands comma, else last 2-dp value
                    for tok in reversed(money):
                        if "," in tok:
                            valuation = parse_indian_decimal(tok)
                            break
                    if valuation is None:
                        valuation = parse_indian_decimal(money[-1])
                    # Price/NAV: last 4-decimal token before valuation
                    for tok in reversed(money[:-1] if len(money) > 1 else money):
                        if re.search(r"\.\d{4}$", tok.replace(",", "")):
                            nav = parse_indian_decimal(tok)
                            break
                    if nav is None and len(money) >= 2:
                        nav = parse_indian_decimal(money[-2])

                name = re.sub(r"\s+", " ", " ".join(name_parts)).strip()
                if name and (current is not None or valuation is not None):
                    holdings.append(
                        FundHolding(
                            amc="EQUITY",
                            folio=folio,
                            scheme_name=name,
                            isin=isin,
                            opening_units=None,
                            closing_units=current if current is not None else Decimal("0"),
                            nav=nav,
                            valuation=valuation if valuation is not None else Decimal("0"),
                            valuation_date=as_on,
                            source_page=page,
                        )
                    )
                i = j
                continue
            i += 1
    return holdings


def _first(pattern: str, text: str, flags=re.I) -> Optional[str]:
    m = re.search(pattern, text, flags)
    return m.group(1).strip() if m else None


def _parse_equity_transactions(text: str, page_map: dict[int, str]) -> list[Transaction]:
    txns: list[Transaction] = []
    # Restrict to CDSL demat transaction pages (before HOLDING STATEMENT / NSDL section)
    start = text.find("DEMAT ACCOUNTS HELD WITH CDSL")
    end = text.find("HOLDING STATEMENT AS ON")
    if start < 0:
        return txns
    section = text[start : end if end > start else len(text)]

    # Determine current BO
    current_folio = "CDSL"
    lines = _lines(section)
    i = 0
    while i < len(lines):
        bo = BO_ID_RE.search(lines[i])
        if bo:
            current_folio = bo.group(1)
        if lines[i] == "No Transaction during the period":
            i += 1
            continue
        if looks_like_isin(lines[i]) and lines[i].startswith("INE"):
            isin = lines[i]
            # Collect name until we hit a transaction keyword or date
            name_parts: list[str] = []
            j = i + 1
            while j < len(lines) and not DATE_DMY.match(lines[j]) and not looks_like_isin(lines[j]):
                if lines[j] in {"ISIN", "Security", "Transaction", "Particulars", "Date", "Op. Bal", "Credit", "Debit", "Cl. Bal", "Stamp", "Duty", "(`)"}:
                    j += 1
                    continue
                if re.search(r"[\u0900-\u097F]", lines[j]):
                    j += 1
                    continue
                # Stop name accumulation when particulars start (PAYOUT, EP-DR, INTDEP)
                if re.match(r"^(PAYOUT|EP-DR|INTDEP|OFF|ON)", lines[j], re.I):
                    break
                name_parts.append(lines[j])
                j += 1
            # May have multiple transactions for same ISIN without repeating ISIN
            while j < len(lines) and not looks_like_isin(lines[j]):
                if BO_ID_RE.search(lines[j]) or lines[j].startswith("DP Name") or lines[j].startswith("STATEMENT OF"):
                    break
                # Find start of a txn description
                desc_parts: list[str] = []
                while j < len(lines) and not DATE_DMY.match(lines[j]) and not looks_like_isin(lines[j]):
                    if lines[j] in {"ISIN", "Security", "Transaction", "Particulars", "Date", "Op. Bal", "Credit", "Debit", "Cl. Bal", "Stamp", "Duty", "(`)"}:
                        j += 1
                        continue
                    if re.search(r"[\u0900-\u097F]", lines[j]):
                        j += 1
                        continue
                    if BO_ID_RE.search(lines[j]):
                        break
                    desc_parts.append(lines[j])
                    j += 1
                if j >= len(lines) or not DATE_DMY.match(lines[j]):
                    break
                date = lines[j]
                j += 1
                nums: list[str] = []
                while j < len(lines) and len(nums) < 5:
                    tok = lines[j]
                    if looks_like_isin(tok) or DATE_DMY.match(tok) or BO_ID_RE.search(tok):
                        break
                    if re.match(r"^(PAYOUT|EP-DR|INTDEP)", tok, re.I):
                        break
                    if tok == "--" or re.match(r"^-?[\d,]+\.\d+$", tok) or tok == "0":
                        nums.append(tok)
                        j += 1
                    else:
                        # skip non-numeric
                        if re.search(r"[\u0900-\u097F]", tok) or tok in {"Stamp", "Duty"}:
                            j += 1
                            continue
                        break
                # Interpret nums: op, credit, debit, close, stamp — with -- placeholders
                slots: list[Optional[Decimal]] = []
                for n in nums[:5]:
                    slots.append(None if n == "--" else parse_indian_decimal(n))
                while len(slots) < 5:
                    slots.append(None)
                op_bal, credit, debit, cl_bal, stamp = slots[:5]
                units = None
                if credit is not None and credit != 0:
                    units = credit
                elif debit is not None and debit != 0:
                    units = -debit
                desc = " ".join(desc_parts).strip()
                desc = re.sub(r"\s+", " ", desc)
                name = re.sub(r"\s+", " ", " ".join(name_parts))
                if desc and date:
                    # page estimate: find date in page_map
                    source_page = 1
                    for p, pt in page_map.items():
                        if date in pt and isin in pt:
                            source_page = p
                            break
                    txns.append(
                        Transaction(
                            amc="EQUITY",
                            folio=current_folio,
                            scheme_name=name or isin,
                            isin=isin,
                            date=date,
                            transaction_type=normalize_demat_txn_type(desc),
                            description=desc,
                            amount=stamp,
                            units=units,
                            nav=None,
                            unit_balance=cl_bal if cl_bal is not None else op_bal,
                            source_page=source_page,
                        )
                    )
                # Continue for next txn under same ISIN
                if j < len(lines) and looks_like_isin(lines[j]):
                    break
                if j < len(lines) and BO_ID_RE.search(lines[j]):
                    break
            i = j
            continue
        i += 1
    return txns


def _folio_map_from_account_details(text: str) -> dict[str, list[tuple[str, str, str]]]:
    """Map ISIN -> list of (amc, folio, scheme_name)."""
    mapping: dict[str, list[tuple[str, str, str]]] = {}
    amc = "unknown"
    scheme = "unknown"
    folio = "unknown"
    for line in _lines(text):
        if line.startswith("AMC Name"):
            amc = line.split(":", 1)[-1].strip()
        elif line.startswith("Scheme Name"):
            scheme = line.split(":", 1)[-1].strip()
        elif line.startswith("Folio No"):
            folio = line.split(":", 1)[-1].strip()
        elif line.startswith("ISIN"):
            isin = line.split(":", 1)[-1].strip()
            if looks_like_isin(isin):
                mapping.setdefault(isin, []).append((amc, folio, scheme))
    return mapping


def _parse_mf_holdings(page_map: dict[int, str], folio_map: dict) -> list[FundHolding]:
    holdings: list[FundHolding] = []
    buffer_pages: list[tuple[int, str]] = []
    collecting = False
    for page, page_text in page_map.items():
        if "MUTUAL FUND UNITS HELD AS ON" in page_text:
            collecting = True
        if collecting:
            buffer_pages.append((page, page_text))
        if collecting and "Load Structures" in page_text:
            break

    as_on = None

    def is_scheme_header(ln: str) -> bool:
        m = re.match(r"^([A-Z0-9]{2,8})\s*-\s*(.+)$", ln)
        if not m:
            return False
        code = m.group(1).upper()
        if code in {"FUND", "PLAN", "GROWTH", "DIRECT", "OPTION", "SMALL", "MIDCAP", "FLEXI"}:
            return False
        return True

    for page, page_text in buffer_pages:
        if as_on is None:
            as_on = _first(r"MUTUAL FUND UNITS HELD AS ON\s+(\d{2}-\d{2}-\d{4})", page_text)
        lines = _lines(page_text)
        # Normalize glued ISIN+folio
        normalized: list[str] = []
        for ln in lines:
            m = re.match(r"^(INF[A-Z0-9]{9})\s+(\S+)$", ln)
            if m:
                normalized.extend([m.group(1), m.group(2)])
            else:
                normalized.append(ln)
        lines = normalized

        i = 0
        while i < len(lines):
            if looks_like_isin(lines[i]) and lines[i].startswith("INF"):
                isin = lines[i]
                # Walk backward for scheme name only (code - name lines / continuation)
                name_parts: list[str] = []
                k = i - 1
                while k >= 0:
                    ln = lines[k]
                    if looks_like_isin(ln) or ln.startswith("ISIN") or ln == "Grand Total":
                        break
                    if ln in {
                        "Scheme Name", "Folio No.", "Closing", "Bal", "(Units)", "NAV (`)",
                        "Cumulative", "Amount", "Invested (in", "INR)", "Valuation (`)",
                        "Unrealised", "Profit/Loss", "Unreali­", "sed", "Profit/", "Loss(%)",
                    }:
                        break
                    if re.search(r"[\u0900-\u097F]", ln):
                        k -= 1
                        continue
                    if parse_indian_decimal(ln) is not None and re.match(r"^-?[\d,]+\.?\d*$", ln.replace(",", "")):
                        break
                    if ln.startswith("MUTUAL FUND") or ln.startswith("Page "):
                        break
                    name_parts.insert(0, ln)
                    k -= 1
                    if is_scheme_header(ln):
                        break
                    if len(name_parts) > 5:
                        break
                # Drop leading junk that isn't part of scheme
                while name_parts and (
                    name_parts[0].startswith("Unreal")
                    or name_parts[0] in {"sed", "Profit/", "Loss(%)"}
                    or re.match(r"^-?[\d,]+\.\d+$", name_parts[0].replace(",", ""))
                ):
                    name_parts.pop(0)

                j = i + 1
                folio = "unknown"
                if j < len(lines):
                    glued = re.match(r"^(\d+[A-Z0-9/]*)\s+([\d,]+\.\d+)$", lines[j])
                    if glued:
                        folio = glued.group(1)
                        lines[j] = glued.group(2)  # units continue as next numeric
                    elif re.match(r"^\d+[A-Z0-9/]*$", lines[j].replace(" ", "")) or re.match(
                        r"^\d+/\d+$", lines[j]
                    ):
                        folio = lines[j]
                        j += 1

                nums: list[Decimal] = []
                while j < len(lines) and len(nums) < 6:
                    if looks_like_isin(lines[j]) or lines[j] == "Grand Total" or lines[j].startswith("Load"):
                        break
                    if is_scheme_header(lines[j]):
                        break
                    if lines[j] in {"Scheme Name", "ISIN", "Folio No.", "Closing", "Bal", "(Units)"}:
                        j += 1
                        continue
                    if re.search(r"[\u0900-\u097F]", lines[j]):
                        j += 1
                        continue
                    d = parse_indian_decimal(lines[j])
                    if d is not None and ("." in lines[j] or "," in lines[j]):
                        nums.append(d)
                        j += 1
                        continue
                    if nums:
                        break
                    j += 1

                if len(nums) >= 4:
                    units, nav, invested, valuation = nums[0], nums[1], nums[2], nums[3]
                    scheme = re.sub(r"\s+", " ", " ".join(name_parts)).strip()
                    amc = "Mutual Fund"
                    if isin in folio_map:
                        for a, f, s in folio_map[isin]:
                            if folio == "unknown" or f == folio:
                                amc = a
                                if folio == "unknown":
                                    folio = f
                                if not scheme or len(scheme) < 5:
                                    scheme = s
                                break
                        else:
                            amc, folio_alt, scheme_alt = folio_map[isin][0]
                            if folio == "unknown":
                                folio = folio_alt
                            if not scheme or len(scheme) < 5:
                                scheme = scheme_alt
                    if scheme:
                        holdings.append(
                            FundHolding(
                                amc=amc,
                                folio=folio,
                                scheme_name=scheme,
                                isin=isin,
                                opening_units=None,
                                closing_units=units,
                                nav=nav,
                                valuation=valuation,
                                valuation_date=as_on,
                                source_page=page,
                                asset_class="mutual_fund",
                                invested_amount=invested,
                                unrealised_pl=nums[4] if len(nums) > 4 else None,
                                unrealised_pl_pct=nums[5] if len(nums) > 5 else None,
                            )
                        )
                i = j
                continue
            i += 1
    return holdings


def _parse_mf_transactions(page_map: dict[int, str], folio_map: dict) -> list[Transaction]:
    txns: list[Transaction] = []
    in_section = False
    current_amc = "unknown"
    current_scheme = "unknown"
    current_isin = None
    current_folio = "unknown"
    current_page = 1

    def is_scheme_header(ln: str) -> bool:
        m = re.match(r"^([A-Z0-9]{2,8})\s*-\s*(.+)$", ln)
        if not m:
            return False
        return m.group(1).upper() not in {"FUND", "PLAN", "GROWTH", "DIRECT", "OPTION", "SMALL", "MIDCAP", "FLEXI"}

    for page, page_text in page_map.items():
        if "MUTUAL FUND UNITS HELD WITH MF/RTA" in page_text:
            in_section = True
        if not in_section:
            continue
        if "MUTUAL FUND UNITS HELD AS ON" in page_text:
            # Still process lines before that marker
            cut = page_text.find("MUTUAL FUND UNITS HELD AS ON")
            page_text = page_text[:cut]
            in_section = False  # after this page's prefix we're done with txns

        current_page = page
        lines = _lines(page_text)
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.endswith("Mutual Fund") or "Mutual Fund" in line and not line.startswith("MUTUAL"):
                if not line.startswith("MUTUAL FUND") and "Units" not in line:
                    current_amc = line.strip()
            if is_scheme_header(line):
                current_scheme = line
            if line.startswith("ISIN"):
                isin = line.split(":", 1)[-1].strip()
                if looks_like_isin(isin):
                    current_isin = isin
                    if isin in folio_map:
                        current_amc, current_folio, sch = folio_map[isin][0]
                        if current_scheme == "unknown":
                            current_scheme = sch
            if line.startswith("Opening Balance"):
                i += 1
                continue
            if line.startswith("Closing Balance"):
                i += 1
                continue

            date_m = re.match(r"^(\d{2}-\d{2}-\d{4})\s+(.+)$", line) or DATE_DMY.match(line)
            if date_m:
                date = date_m.group(1)
                desc_parts: list[str] = []
                j = i + 1
                if date_m.lastindex and date_m.lastindex >= 2 and date_m.group(2):
                    desc_parts.append(date_m.group(2).strip())
                # Multi-line description until we hit a money amount
                while j < len(lines) and not (
                    parse_indian_decimal(lines[j]) is not None
                    and ("," in lines[j] or re.match(r"^\d+\.\d{2,4}$", lines[j].replace(",", "")) or lines[j] in {"999.95", "0", ".05"})
                ):
                    if DATE_DMY.match(lines[j]) or lines[j].startswith("Closing") or lines[j].startswith("Opening"):
                        break
                    if looks_like_isin(lines[j]) or lines[j].startswith("ISIN") or is_scheme_header(lines[j]):
                        break
                    if re.search(r"[\u0900-\u097F]", lines[j]):
                        j += 1
                        continue
                    if lines[j] in {"Date", "Transaction Description", "Amount (`)", "NAV (`)", "Price (`)", "Units", "Stamp", "Duty (`)", "Income", "Capital"}:
                        j += 1
                        continue
                    desc_parts.append(lines[j])
                    j += 1
                    if len(desc_parts) > 12:
                        break
                nums: list[Decimal] = []
                while j < len(lines) and len(nums) < 7:
                    if DATE_DMY.match(lines[j]) or lines[j].startswith("Closing") or lines[j].startswith("Opening"):
                        break
                    if looks_like_isin(lines[j]) or lines[j].startswith("ISIN"):
                        break
                    d = parse_indian_decimal(lines[j])
                    if d is not None and (re.search(r"[\d.]", lines[j])):
                        nums.append(d)
                        j += 1
                    else:
                        if re.search(r"[\u0900-\u097F]", lines[j]):
                            j += 1
                            continue
                        break
                desc = re.sub(r"\s+", " ", " ".join(desc_parts)).strip()
                if desc and current_isin and len(nums) >= 3:
                    amount = nums[0]
                    nav = nums[1]
                    units = nums[3] if len(nums) >= 4 else nums[2]
                    if len(nums) >= 4 and abs(nums[2] - nav) < Decimal("0.0001"):
                        units = nums[3]
                    folio = current_folio
                    if current_isin in folio_map:
                        folio = folio_map[current_isin][0][1]
                    txns.append(
                        Transaction(
                            amc=current_amc,
                            folio=folio,
                            scheme_name=current_scheme,
                            isin=current_isin,
                            date=date,
                            transaction_type=normalize_transaction(desc),
                            description=desc,
                            amount=amount,
                            units=units,
                            nav=nav,
                            unit_balance=None,
                            source_page=current_page,
                        )
                    )
                i = j
                continue
            i += 1
        if not in_section:
            break
    return txns


def parse_cdsl_cas(path: str | Path) -> CdslParseResult:
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(source)
    pages = _extract_pages(source)
    full = "\n".join(pages[i] for i in sorted(pages))
    warnings: list[str] = []
    meta = CdslMetadata()

    ok, matched = classify_cdsl_cas(pages)
    if not ok:
        raise ValueError(
            "This doesn't appear to be a CDSL Consolidated Account Statement."
        )
    meta.successful_sections.append("classification")

    cas_id = CAS_ID_RE.search(full)
    if cas_id:
        meta.cas_id = cas_id.group(1)
    meta.statement_start, meta.statement_end = _find_period(full)
    if meta.statement_start and meta.statement_end:
        meta.successful_sections.append("statement_period")
    else:
        meta.failed_sections.append("statement_period")
        warnings.append("Could not detect statement period")

    meta.pan_masked = _mask_pan(full)
    # Holder name near summary
    m = re.search(r"Name/Joint Name \(s\).*?\n([A-Za-z .]+)\n", full, re.S)
    if m:
        meta.holder_name = m.group(1).strip()
    else:
        m = re.search(r"In the single name of\s*\n([A-Z ]+)\s*\(", full)
        if m:
            meta.holder_name = m.group(1).strip().title()

    _parse_summary_values(full, meta)
    if meta.total_portfolio_value is not None:
        meta.successful_sections.append("portfolio_summary")
    else:
        meta.failed_sections.append("portfolio_summary")
        warnings.append("Portfolio summary values not found")

    _parse_accounts(full, meta)
    if meta.demat_accounts:
        meta.successful_sections.append("demat_accounts")
    else:
        meta.failed_sections.append("demat_accounts")
        warnings.append("Demat accounts not extracted")

    _parse_snapshots(full, meta)
    if meta.snapshots:
        meta.successful_sections.append("portfolio_snapshots")

    folio_map = _folio_map_from_account_details(full)

    equity_holdings = _parse_equity_holdings(full, pages)
    for h in equity_holdings:
        h.asset_class = "equity"
    if equity_holdings:
        meta.successful_sections.append("equity_holdings")
    else:
        meta.failed_sections.append("equity_holdings")
        warnings.append("No equity holdings extracted")

    equity_txns = _parse_equity_transactions(full, pages)
    if equity_txns:
        meta.successful_sections.append("equity_transactions")
    else:
        # May legitimately have no txns for some accounts — only warn if CDSL section lacked nil markers
        if "STATEMENT OF TRANSACTIONS" in full and "No Transaction during the period" not in full:
            meta.failed_sections.append("equity_transactions")
            warnings.append("Equity transactions section present but none extracted")
        else:
            meta.successful_sections.append("equity_transactions")

    mf_holdings = _parse_mf_holdings(pages, folio_map)
    if mf_holdings:
        meta.successful_sections.append("mf_holdings")
    else:
        meta.failed_sections.append("mf_holdings")
        warnings.append("No mutual fund holdings extracted")

    mf_txns = _parse_mf_transactions(pages, folio_map)
    if mf_txns:
        meta.successful_sections.append("mf_transactions")
    else:
        meta.failed_sections.append("mf_transactions")
        warnings.append("Mutual fund transactions not extracted")

    holdings = equity_holdings + mf_holdings
    transactions = equity_txns + mf_txns

    if meta.failed_sections and holdings:
        meta.status = "partial"
    elif not holdings:
        meta.status = "failed"
        warnings.append("No holdings confidently parsed")
    else:
        meta.status = "processed"

    return CdslParseResult(
        holdings=holdings,
        transactions=transactions,
        pages=pages,
        warnings=warnings,
        metadata=meta,
    )
