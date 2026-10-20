"""Synthetic HTML schema fixture; no external network in tests."""
from datetime import date
from copy import deepcopy

import httpx
import pytest

from ai_cio.services.mutual_funds.cache import PublicDataCache
from ai_cio.services.mutual_funds.published_performance import (
    fetch_ppfas_published_performance, parse_ppfas_published_performance,
)

URL = "https://amc.ppfas.com/downloads/digital-factsheet/2026/september-2026/"
IDENTITY = {"isin": "INF879O01027", "scheme_code": 122639, "identity_status": "verified", "plan": "direct", "option": "growth"}
AS_OF = date(2026, 10, 20)


def html():
    return b'''<div id="mySidepanelPPFCF" class="sidepanel">
    <h2>Parag Parikh Flexi Cap Fund</h2>
    <button>Fund Details</button><table><tr><td>Benchmark Name:</td><td>NIFTY 500 (TRI)</td></tr>
    <tr><td>NAV as on September 30, 2026:</td></tr></table>
    <button>Fund Performance</button><table>
    <tr><td>Compounded<br>Annualised Returns</td><td>Scheme Returns % - Regular</td><td>Scheme Returns % - Direct</td><td>Benchmark Returns % -</td></tr>
    <tr><td>1 Year</td><td>5.00%</td><td>6.00%</td><td>7.00%</td></tr>
    <tr><td>3 Years</td><td>8.00%</td><td>9.00%</td><td>10.00%</td></tr>
    <tr><td>5 Years</td><td>11.00%</td><td>12.00%</td><td>13.00%</td></tr></table>
    <button>SIP Investment Performance</button><table><tr><td>1 Year</td><td>99.00%</td><td>98.00%</td><td>97.00%</td></tr></table></div>
    <div id="mySidepanelPPLCF" class="sidepanel"><h2>Different Fund</h2></div>'''


def parse(content=None, identity=None, url=URL, as_of=AS_OF):
    return parse_ppfas_published_performance(content or html(), identity or IDENTITY, source_url=url, as_of=as_of)


def test_exact_plan_numeric_columns_and_basis_are_preserved():
    out = parse()
    assert out["available"] is True
    assert out["plan"] == "direct"
    assert out["option_verified"] is False
    assert out["option_basis"] == "not_stated_in_published_table"
    assert out["observed_on"] == "2026-09-30"
    assert [(r["fund_return_pct"], r["benchmark_return_pct"], r["excess_return_pp"]) for r in out["returns"]] == [(6, 7, -1), (9, 10, -1), (12, 13, -1)]
    assert all(r["start_date"] is None and r["basis"] == "amc_published_reported" for r in out["returns"])
    assert out["rolling"] is None and out["benchmark_history"] == []
    assert len(out["sha256"]) == 64


@pytest.mark.parametrize("field,value", [("isin", "INF000000000"), ("scheme_code", 999), ("plan", "regular"), ("option", "idcw"), ("identity_status", "unresolved")])
def test_wrong_isin_code_or_plan_option_is_never_silently_matched(field, value):
    identity = deepcopy(IDENTITY)
    identity[field] = value
    with pytest.raises(ValueError):
        parse(identity=identity)


@pytest.mark.parametrize("mutation", ["wrong_title", "wrong_benchmark", "swapped_columns", "missing_period", "duplicate_period", "nan", "no_date", "future_date", "duplicate_table", "sip_only"])
def test_schema_changes_fail_closed(mutation):
    content = html()
    if mutation == "wrong_title":
        content = content.replace(b"Parag Parikh Flexi Cap Fund", b"Unrelated Scheme")
    elif mutation == "wrong_benchmark":
        content = content.replace(b"NIFTY 500 (TRI)", b"NIFTY 50 PRICE")
    elif mutation == "swapped_columns":
        content = content.replace(b"Scheme Returns % - Direct", b"Scheme Returns % - Regular")
    elif mutation == "missing_period":
        content = content.replace(b"5 Years", b"10 Years")
    elif mutation == "duplicate_period":
        content = content.replace(b"5 Years", b"3 Years")
    elif mutation == "nan":
        content = content.replace(b"6.00%", b"NaN%")
    elif mutation == "no_date":
        content = content.replace(b"NAV as on", b"NAV observed")
    elif mutation == "future_date":
        content = content.replace(b"September 30, 2026", b"September 30, 2027")
    elif mutation == "duplicate_table":
        content = content.replace(b"SIP Investment Performance", b"Fund Performance")
    else:
        content = content.replace(b">Fund Performance<", b">SIP Investment Performance<")
    with pytest.raises(ValueError):
        parse(content)


@pytest.mark.parametrize("url", [
    "http://amc.ppfas.com/downloads/digital-factsheet/2026/september-2026/",
    "https://example.test/downloads/digital-factsheet/2026/september-2026/",
    URL + "?unexpected=1", URL + "#fragment",
    "https://amc.ppfas.com:443/downloads/digital-factsheet/2026/september-2026/",
    "https://amc.ppfas.com/downloads/digital-factsheet/2025/september-2026/",
])
def test_untrusted_or_inconsistent_source_url_rejected(url):
    with pytest.raises(ValueError):
        parse(url=url)


def test_future_document_and_stale_flag_are_separate():
    with pytest.raises(ValueError):
        parse(as_of=date(2026, 9, 29))
    assert parse(as_of=date(2027, 1, 1))["stale"] is True


class Provider:
    def __init__(self, path, error=None):
        self.cache = PublicDataCache(path)
        self.urls = []
        self.error = error

    def _get(self, url, *, json_response):
        self.urls.append(url)
        assert json_response is False
        if self.error:
            raise self.error
        return html()


def test_fetch_reuses_shared_month_cache_and_never_contacts_arbitrary_host(tmp_path):
    provider = Provider(tmp_path)
    first = fetch_ppfas_published_performance(provider, IDENTITY, as_of=AS_OF)
    second = fetch_ppfas_published_performance(provider, IDENTITY, as_of=AS_OF)
    assert first["available"] and second["cache_status"] == "hit"
    assert provider.urls == [URL]
    assert fetch_ppfas_published_performance(provider, {**IDENTITY, "isin": "INF000000000"}, as_of=AS_OF) is None
    assert provider.urls == [URL]


def test_http_failure_has_three_month_bound_and_returns_none(tmp_path):
    provider = Provider(tmp_path, error=httpx.ConnectError("fixture unavailable"))
    assert fetch_ppfas_published_performance(provider, IDENTITY, as_of=AS_OF) is None
    assert len(provider.urls) == 3
    assert all(url.startswith("https://amc.ppfas.com/downloads/digital-factsheet/") for url in provider.urls)
