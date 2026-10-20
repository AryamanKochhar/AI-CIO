"""Official Nippon Small Cap reported plan comparisons, never synthetic TRI.

The monthly folder can refer to a factsheet whose performance date is the prior
month end. The date stated in the table is authoritative and shown separately.
The publisher currently calls its fee BER; this adapter does not relabel it TER.
"""
from __future__ import annotations

from datetime import date, datetime
import hashlib
import re
from urllib.parse import urljoin, urlparse

import httpx

from .catalogued_disclosures import NIPPON_INDEX, _spec
from .official_adapters import _Links
from .published_performance import MAX_HTML_BYTES, MONTHS, _Tables, _percent, _text


def discover_nippon_factsheets(html: str, *, as_of: date):
    parser = _Links(); parser.feed(html)
    result = []
    for link in parser.links:
        absolute = urljoin(NIPPON_INDEX, link)
        parsed = urlparse(absolute)
        match = re.fullmatch(r"/InvestorServices/FactsheetsDocuments/Fundamentals-([A-Za-z]+)-(\d{4})/index\.html", parsed.path)
        if (parsed.scheme != "https" or parsed.hostname != "mf.nipponindiaim.com" or parsed.port is not None
                or parsed.username or parsed.password or parsed.query or parsed.fragment or not match):
            continue
        month, year = match.groups()
        if month.lower() not in MONTHS:
            continue
        when = date(int(year), MONTHS[month.lower()], 1)
        if when <= as_of:
            result.append((when, urljoin(absolute, "Innerpage/Small-Cap.html")))
    return sorted(set(result), reverse=True)


def parse_nippon_published(html: str | bytes, identity: dict, *, source_url: str, as_of: date):
    spec = _spec(identity)
    if not spec or spec["publisher"] != "nippon":
        raise ValueError("No tested published comparison for this exact verified identity")
    parsed = urlparse(source_url)
    match = re.fullmatch(r"/InvestorServices/FactsheetsDocuments/Fundamentals-([A-Za-z]+)-(\d{4})/Innerpage/Small-Cap\.html", parsed.path)
    if (parsed.scheme != "https" or parsed.hostname != "mf.nipponindiaim.com" or parsed.port is not None
            or parsed.username or parsed.password or parsed.query or parsed.fragment or not match):
        raise ValueError("Published comparison requires the configured official scheme URL")
    month, year = match.groups()
    if month.lower() not in MONTHS:
        raise ValueError("Unknown factsheet month")
    folder_date = date(int(year), MONTHS[month.lower()], 1)
    raw = html if isinstance(html, bytes) else html.encode("utf-8")
    if len(raw) > MAX_HTML_BYTES:
        raise ValueError("Published factsheet exceeds adapter size bound")
    text = raw.decode("utf-8-sig")
    titles = re.findall(r"<title\b[^>]*>(.*?)</title>", text, re.S | re.I)
    if len(titles) != 1 or _text(titles[0]).upper() != spec["title"]:
        raise ValueError("Factsheet title does not match the configured scheme")
    parser = _Tables(); parser.feed(text)
    flat = _text(" ".join(parser.all_text))
    dates = re.findall(r"Performance as on ([A-Za-z]+ \d{1,2}, \d{4})", flat, re.I)
    if len(dates) != 1:
        raise ValueError("Expected one explicit published performance observation date")
    observed = datetime.strptime(dates[0], "%B %d, %Y").date()
    if observed > as_of or abs((folder_date - observed).days) > 35 or folder_date > as_of:
        raise ValueError("Published performance date differs from the monthly folder or is in the future")
    benchmark_names = [row[1] for _, rows in parser.tables for row in rows
                       if len(row) == 2 and row[0].lower() == "benchmark name:"]
    if (len(benchmark_names) != 1
            or re.sub(r"[^a-z0-9]", "", benchmark_names[0].lower()) != "niftysmallcap250tri"):
        raise ValueError("Published benchmark identity is not the configured total-return index")
    tables = [rows for _, rows in parser.tables if rows and len(rows[0]) == 4
              and [cell.lower() for cell in rows[0]] == ["compounded annualised returns", "scheme returns % - regular",
                                                        "scheme returns % - direct", "benchmark returns %"]]
    if len(tables) != 1:
        raise ValueError("Published plan/benchmark performance table is missing or ambiguous")
    returns = []; seen = set()
    for row in tables[0][1:]:
        if not row:
            continue
        period = re.fullmatch(r"returns for last (1|3|5) years?", row[0].lower())
        if not period:
            continue
        if len(row) != 4 or period.group(1) in seen:
            raise ValueError("Published trailing period is duplicated or malformed")
        years = int(period.group(1)); seen.add(period.group(1))
        # The table header explicitly defines percentages; unlike PPFAS, these
        # cells omit the '%' suffix. Do not accept mixed or arbitrary text.
        if any(not re.fullmatch(r"[+-]?\d+(?:\.\d+)?", value) for value in row[1:]):
            raise ValueError("Published performance cell is not a finite percentage")
        fund, benchmark = _percent(row[2] + "%"), _percent(row[3] + "%")
        returns.append({"period": f"{years}y", "window_years": years, "start_date": None,
                        "end_date": observed.isoformat(), "fund_return_pct": float(fund),
                        "benchmark_return_pct": float(benchmark), "excess_return_pp": float(fund - benchmark),
                        "annualized": True, "return_basis": "AMC published compounded annualised plan return",
                        "basis": "amc_published_reported",
                        "calculation": "excess_return_pp = published fund return minus published benchmark return"})
    if seen != {"1", "3", "5"}:
        raise ValueError("Published comparison requires the tested 1/3/5-year rows")
    return {"available": True, "status": "reported_comparison_only", "adapter": "nippon-published-plan-comparison-v1",
            "scheme_code": spec["scheme_code"], "scheme_name": "Nippon India Small Cap Fund", "isin": identity["isin"],
            "plan": "direct", "requested_option": "growth", "option_basis": "not_stated_in_published_table",
            "option_verified": False, "observed_on": observed.isoformat(), "source_url": source_url,
            "source_id": f"mf_nippon_published_{spec['scheme_code']}_{observed.isoformat()}",
            "sha256": hashlib.sha256(raw).hexdigest(), "basis": "amc_published_reported",
            "benchmark": {"id": spec["benchmark_id"], "name": benchmark_names[0], "kind": "TRI", "source_url": source_url},
            "returns": returns, "rolling": None, "benchmark_history": [], "stale": (as_of - observed).days > 62,
            "limitations": ["AMC-reported plan comparison, separate from independently computed NAV/TRI performance.",
                            "The plan performance table does not explicitly state Growth/IDCW or exact starting market dates.",
                            "The stated performance date may precede the factsheet folder month; the stated date is retained.",
                            "Trailing values do not provide daily TRI observations, rolling consistency or a benchmark chart.",
                            "The publisher's BER fee label is not treated as TER."]}


def fetch_nippon_published(provider, identity: dict, *, as_of: date):
    spec = _spec(identity)
    if not spec or spec["publisher"] != "nippon":
        return None
    try:
        index = provider.cache.get("nippon:portfolio:index:v1", 86400,
                                   lambda: provider._get(NIPPON_INDEX, json_response=False).decode("utf-8-sig"),
                                   max_stale=30 * 86400)
        for _, url in discover_nippon_factsheets(index["payload"], as_of=as_of)[:2]:
            try:
                raw = provider.cache.get(f"nippon:published:{url}:v1", 86400,
                                         lambda: provider._get(url, json_response=False).decode("utf-8-sig"),
                                         max_stale=7 * 86400)
                result = parse_nippon_published(raw["payload"], identity, source_url=url, as_of=as_of)
                result.update({"retrieved_at": raw["retrieved_at"], "cache_status": raw["cache_status"],
                               "cache_stale": bool(raw.get("stale"))})
                return result
            except (ValueError, OSError, RuntimeError, httpx.HTTPError):
                continue
    except (ValueError, OSError, RuntimeError, httpx.HTTPError):
        pass
    return None
