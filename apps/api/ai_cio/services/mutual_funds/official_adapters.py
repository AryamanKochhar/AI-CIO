"""Narrow official AMC adapters with fail-closed schema and identity checks.

PPFAS publishes per-scheme monthly XLSX portfolios. HDFC and other AMCs need
their own tested layouts (some currently reject automated requests); the system
never claims universal holdings coverage from MFAPI or an AMC name alone.
"""
from __future__ import annotations

from base64 import b64encode, b64decode
from datetime import date, datetime
import hashlib
from html.parser import HTMLParser
import re
from urllib.parse import urljoin, urlparse

from .disclosures import ISIN, _xlsx_rows, iso_date, number, validate_disclosure

PPFAS_INDEX = "https://amc.ppfas.com/downloads/portfolio-disclosure/index.php"
PPFAS_SCHEMES = {
    "INF879O01027": ("PPFCF", "parag parikh flexi cap fund"),
    "INF879O01100": ("PPTSF", "parag parikh elss tax saver fund"),
}


class _Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            for key, value in attrs:
                if key == "href" and value:
                    self.links.append(value)


def discover_ppfas(html: str, prefix: str, *, as_of: date) -> list[tuple[date, str]]:
    parser = _Links()
    parser.feed(html)
    candidates = []
    for link in parser.links:
        absolute = urljoin(PPFAS_INDEX, link)
        parsed = urlparse(absolute)
        if parsed.scheme != "https" or parsed.hostname != "amc.ppfas.com":
            continue
        match = re.search(r"/" + re.escape(prefix) + r"_PPFAS_Monthly_Portfolio_Report_([A-Za-z]+)_(\d{1,2})_(\d{4})\.xlsx$", parsed.path)
        if not match:
            continue
        try:
            observed = datetime.strptime(" ".join(match.groups()), "%B %d %Y").date()
        except ValueError:
            continue
        if observed <= as_of:
            candidates.append((observed, absolute))
    return sorted(set(candidates), reverse=True)


def parse_ppfas_portfolio(content: bytes, identity: dict, *, source_url: str,
                          observed_on: date, as_of: date) -> dict:
    spec = PPFAS_SCHEMES.get(identity.get("isin"))
    if not spec:
        raise ValueError("No tested official portfolio adapter for this exact scheme ISIN")
    rows = _xlsx_rows(content, allow_cached_formulas=True)
    text = " ".join(str(cell) for row in rows[:5] for cell in row).lower()
    normalized_text = re.sub(r"[^a-z0-9 ]", " ", text)
    normalized_text = re.sub(r"\s+", " ", normalized_text)
    expected = spec[1]
    # The AMC renamed Tax Saver to ELSS Tax Saver; both are the same explicitly
    # configured scheme, not a fuzzy cross-fund name match.
    acceptable = [expected]
    if spec[0] == "PPTSF":
        acceptable.append("parag parikh tax saver fund")
    if not any(label in normalized_text for label in acceptable):
        raise ValueError("Published portfolio title does not match the configured scheme")
    date_match = re.search(r"statement as on\s+([A-Za-z]+\s+\d{1,2},?\s+\d{4})", text)
    if not date_match or datetime.strptime(date_match.group(1).replace(",", ""), "%B %d %Y").date() != observed_on:
        raise ValueError("Published portfolio observation date differs from the download listing")
    header_index = None
    indices = {}
    for i, row in enumerate(rows[:12]):
        clean = [re.sub(r"\s+", " ", str(cell)).strip().lower() for cell in row]
        if "isin" in clean and "name of the instrument" in clean and "% to net assets" in clean:
            header_index = i
            indices = {name: clean.index(name) for name in ("isin", "name of the instrument", "% to net assets", "industry / rating")}
            break
    if header_index is None:
        raise ValueError("PPFAS disclosure column schema has changed")
    holdings = []
    asset = "unknown"
    for row in rows[header_index + 1:]:
        def value(key):
            idx = indices[key]
            return str(row[idx]).strip() if idx < len(row) else ""
        name, isin = value("name of the instrument"), value("isin").upper()
        lower = name.lower()
        if not isin:
            if "equity & equity" in lower:
                asset = "equity"
            elif "money market instruments" in lower or "debt instruments" in lower or "government securities" in lower:
                asset = "debt"
            elif "reits" in lower or "invits" in lower:
                asset = "fund"
            continue
        if not ISIN.fullmatch(isin):
            continue
        raw = value("% to net assets")
        if raw.startswith("$") and raw.endswith("%"):
            # AMC notation '$0.00%' means less than 0.005%, not an exact zero.
            # Leave that small exposure unknown rather than inventing its value.
            continue
        try:
            weight = number(raw, minimum=0, maximum=1) * 100
        except ValueError:
            continue
        if weight > 0:
            holdings.append({"isin": isin, "name": name, "weight_pct": weight,
                             "asset_class": asset, "sector": value("industry / rating") or None})
    record = validate_disclosure({"scheme_code": identity["scheme_code"], "scheme_isin": identity["isin"],
                                 "source_url": source_url, "observed_on": observed_on.isoformat(),
                                 "holdings": holdings}, as_of=as_of)
    record.update({"provenance": "official_publisher_fetched", "verification": "Downloaded directly from the configured AMC HTTPS host; scheme title, statement date and column schema validated.",
                   "sha256": hashlib.sha256(content).hexdigest(), "adapter": "ppfas-monthly-xlsx-v1",
                   "coverage_note": "Identified disclosed positive long-security weights only; cash, net receivables, rounding markers and unsupported instruments remain unmapped. Not a netted derivative-risk calculation."})
    return record


def fetch_ppfas_disclosure(provider, identity: dict, *, as_of: date) -> dict | None:
    spec = PPFAS_SCHEMES.get(identity.get("isin"))
    if not spec:
        return None
    index = provider.cache.get("ppfas:index:v1", 86400,
                               lambda: provider._get(PPFAS_INDEX, json_response=False).decode("utf-8"),
                               max_stale=30 * 86400)
    candidates = discover_ppfas(index["payload"], spec[0], as_of=as_of)
    if not candidates:
        return None
    observed, url = candidates[0]
    key = f"ppfas:portfolio:{spec[0]}:{observed.isoformat()}:v1"
    raw = provider.cache.get(key, 7 * 86400,
                             lambda: b64encode(provider._get(url, json_response=False)).decode("ascii"),
                             max_stale=180 * 86400)
    result = parse_ppfas_portfolio(b64decode(raw["payload"], validate=True), identity,
                                  source_url=url, observed_on=observed, as_of=as_of)
    result["retrieved_at"] = raw["retrieved_at"]
    result["cache_status"] = raw["cache_status"]
    return result
