"""Exact-scheme adapters for directly fetched Nippon and PGIM disclosures.

These layouts use different percentage units. Nippon's numeric Excel fraction
is multiplied by 100; PGIM's published percentage-point cell is not. Neither is
normalized to a 100% equity-only sample. Only ISIN-identified long securities
enter overlap calculations; the remaining scheme NAV stays explicitly unknown.
"""
from __future__ import annotations

from base64 import b64decode, b64encode
from datetime import date, datetime
import hashlib
import re
from urllib.parse import unquote, urljoin, urlparse

from .disclosures import ISIN, _xlsx_rows, number, validate_disclosure
from .official_adapters import _Links

NIPPON_INDEX = "https://mf.nipponindiaim.com/investor-service/downloads/factsheet-portfolio-and-other-disclosures/"
PGIM_LISTING = "https://www.pgimindia.com/api/v1/brochure/published/disclosure"
SCHEMES = {
    "INF204K01K15": {"publisher": "nippon", "scheme_code": 118778, "title": "NIPPON INDIA SMALL CAP FUND",
                     "sheet": "SC", "portfolio_id": "RLMF200", "benchmark": "NIFTY Smallcap 250 TRI",
                     "benchmark_id": "NIFTYSMALLCAP250TRI"},
    "INF663L01DV3": {"publisher": "pgim", "scheme_code": 125307, "title": "PGIM INDIA MIDCAP FUND",
                     "sheet": "Mid Cap", "benchmark": "Nifty Midcap 150 TRI", "benchmark_id": "NIFTYMIDCAP150TRI"},
}


def _spec(identity: dict):
    spec = SCHEMES.get(identity.get("isin"))
    if not spec or identity.get("identity_status") != "verified":
        return None
    if (str(identity.get("scheme_code")) != str(spec["scheme_code"])
            or identity.get("plan") != "direct" or identity.get("option") != "growth"):
        return None
    return spec


def _clean(value):
    return re.sub(r"\s+", " ", str(value)).strip()


def discover_nippon(html: str, *, as_of: date):
    parser = _Links(); parser.feed(html)
    result = []
    for link in parser.links:
        absolute = urljoin(NIPPON_INDEX, link)
        parsed = urlparse(absolute)
        if (parsed.scheme != "https" or parsed.hostname != "mf.nipponindiaim.com" or parsed.port is not None
                or parsed.username or parsed.password or parsed.query or parsed.fragment):
            continue
        match = re.fullmatch(r"/InvestorServices/FactsheetsDocuments/NIMF-MONTHLY-PORTFOLIO-(\d{1,2})-([A-Za-z]{3})-(\d{2})\.xls[x]?", parsed.path, re.I)
        if not match:
            continue
        try:
            observed = datetime.strptime("-".join(match.groups()), "%d-%b-%y").date()
        except ValueError:
            continue
        if observed <= as_of:
            result.append((observed, absolute))
    return sorted(set(result), reverse=True)


def discover_pgim(payload: dict, *, as_of: date):
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise ValueError("PGIM published disclosure listing has changed schema")
    result = []
    for group in payload["data"]:
        if group.get("tabId") != 12 or group.get("tabName") != "Equity":
            continue
        for item in group.get("content", []):
            title = str(item.get("title") or "")
            match = re.fullmatch(r"PGIM INDIA MIDCAP FUND ([A-Za-z]{3}) (\d{4})", title)
            if not match or item.get("displayStatus") is not True or item.get("disclosureTab") != 12:
                continue
            try:
                observed = datetime.strptime(item["dateMonthYear"], "%d %B %Y").date()
                title_month = datetime.strptime(" ".join(match.groups()), "%b %Y").date()
            except (KeyError, TypeError, ValueError):
                continue
            if (observed.year, observed.month) != (title_month.year, title_month.month) or observed > as_of:
                continue
            url = str(item.get("pdfPath") or "")
            parsed = urlparse(url)
            expected = "/api/v1/brochure/about-us/image/" + title + ".xlsx"
            if (parsed.scheme != "https" or parsed.hostname != "www.pgimindia.com" or parsed.port is not None
                    or parsed.username or parsed.password or parsed.query or parsed.fragment
                    or unquote(parsed.path) != expected):
                continue
            result.append((observed, url))
    return sorted(set(result), reverse=True)


def parse_catalogued_portfolio(content: bytes, identity: dict, *, source_url: str,
                               observed_on: date, as_of: date) -> dict:
    spec = _spec(identity)
    if spec is None:
        raise ValueError("No tested official portfolio adapter for this verified identity")
    publisher = spec["publisher"]
    parsed_url = urlparse(source_url)
    if publisher == "nippon":
        if (observed_on, source_url) not in discover_nippon(f'<a href="{source_url}">portfolio</a>', as_of=as_of):
            raise ValueError("Nippon source URL does not identify the dated official monthly disclosure")
    elif (parsed_url.scheme != "https" or parsed_url.hostname != "www.pgimindia.com"
          or parsed_url.username or parsed_url.password or parsed_url.port is not None
          or parsed_url.query or parsed_url.fragment
          or unquote(parsed_url.path) != "/api/v1/brochure/about-us/image/" + spec["title"] + " " + observed_on.strftime("%b %Y") + ".xlsx"):
        raise ValueError("PGIM source URL does not identify the configured dated scheme workbook")
    rows = _xlsx_rows(content, allow_cached_formulas=True, sheet_name=spec["sheet"])
    opening = " ".join(_clean(cell) for row in rows[:12] for cell in row)
    if spec["title"] not in opening.upper():
        raise ValueError("Published portfolio title does not match the configured scheme")
    if publisher == "nippon" and not rows[0][0] == spec["portfolio_id"]:
        raise ValueError("Nippon scheme portfolio identifier has changed")
    matches = re.findall(r"Portfolio Statement as on\s+([A-Za-z]+\s+\d{1,2},\s*\d{4})", opening, re.I)
    if len(matches) != 1:
        raise ValueError("Expected a unique publisher portfolio observation date")
    observed = datetime.strptime(re.sub(r",\s*", ",", matches[0]), "%B %d,%Y").date()
    if observed != observed_on or observed > as_of:
        raise ValueError("Workbook observation date differs from the official listing")
    header = None
    for index, row in enumerate(rows[:16]):
        clean = [_clean(cell).lower() for cell in row]
        name_header = "name of the instrument" if publisher == "nippon" else "name of instrument"
        sector_header = "industry / rating" if publisher == "nippon" else "industry/rating"
        weight_header = "% to nav" if publisher == "nippon" else "% to net assets"
        required = ("isin", name_header, sector_header, weight_header)
        if all(clean.count(name) == 1 for name in required):
            header = index, {key: clean.index(key) for key in required}
            break
    if header is None:
        raise ValueError("Official disclosure column schema has changed")
    index, columns = header
    name_key, sector_key, weight_key = name_header, sector_header, weight_header
    holdings = []; asset = "unknown"
    for row in rows[index + 1:]:
        def cell(key):
            offset = columns[key]
            return _clean(row[offset]) if offset < len(row) else ""
        name, isin = cell(name_key), cell("isin").upper()
        if not isin:
            lower = name.lower()
            if "equity & equity" in lower:
                asset = "equity"
            elif any(label in lower for label in ("money market", "debt instruments", "government securities")):
                asset = "debt"
            elif any(label in lower for label in ("mutual fund", "reits", "invits")):
                asset = "fund"
            continue
        if not ISIN.fullmatch(isin):
            continue
        weight = number(cell(weight_key), minimum=0, maximum=1 if publisher == "nippon" else 100)
        if publisher == "nippon":
            weight *= 100
        if weight > 0:
            holdings.append({"isin": isin, "name": name, "weight_pct": weight,
                             "asset_class": asset, "sector": cell(sector_key) or None})
    all_text = " ".join(_clean(cell) for row in rows for cell in row)
    normalized = re.sub(r"[^a-z0-9]", "", all_text.lower())
    if re.sub(r"[^a-z0-9]", "", spec["benchmark"].lower()) not in normalized:
        raise ValueError("Official workbook does not confirm the tested benchmark identity")
    record = validate_disclosure({"scheme_code": identity["scheme_code"], "scheme_isin": identity["isin"],
                                 "source_url": source_url, "observed_on": observed_on.isoformat(),
                                 "holdings": holdings, "benchmark_id": spec["benchmark_id"],
                                 "benchmark_name": spec["benchmark"], "benchmark_source_url": source_url}, as_of=as_of)
    record.update({"provenance": "official_publisher_fetched", "adapter": f"{publisher}-monthly-xlsx-v1",
                   "verification": "Downloaded directly from the configured AMC HTTPS host; exact ISIN configuration, scheme title, statement date, worksheet and column schema validated.",
                   "sha256": hashlib.sha256(content).hexdigest(),
                   "coverage_note": "Full-scheme NAV weights of identified positive long securities only. Cash, repo without an ISIN, receivables and unsupported instruments remain unmapped; no equity-only renormalization or netted derivative-risk estimate."})
    return record


def fetch_catalogued_disclosure(provider, identity: dict, *, as_of: date) -> dict | None:
    spec = _spec(identity)
    if spec is None:
        return None
    publisher = spec["publisher"]
    if publisher == "nippon":
        listing = provider.cache.get("nippon:portfolio:index:v1", 86400,
                                     lambda: provider._get(NIPPON_INDEX, json_response=False).decode("utf-8-sig"),
                                     max_stale=30 * 86400)
        candidates = discover_nippon(listing["payload"], as_of=as_of)
    else:
        listing = provider.cache.get("pgim:portfolio:index:v1", 86400, provider._post_disclosure_listing,
                                     max_stale=30 * 86400)
        candidates = discover_pgim(listing["payload"], as_of=as_of)
    if not candidates:
        return None
    observed, url = candidates[0]
    raw = provider.cache.get(f"{publisher}:portfolio:{observed.isoformat()}:v1", 7 * 86400,
                             lambda: b64encode(provider._get(url, json_response=False)).decode("ascii"),
                             max_stale=180 * 86400)
    result = parse_catalogued_portfolio(b64decode(raw["payload"], validate=True), identity,
                                       source_url=url, observed_on=observed, as_of=as_of)
    result.update({"retrieved_at": raw["retrieved_at"], "cache_status": raw["cache_status"]})
    return result
