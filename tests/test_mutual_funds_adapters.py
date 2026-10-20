"""Identity, public-cache and disclosure provenance boundaries without network."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from io import BytesIO
import json
import threading
import time
from zipfile import ZipFile

import httpx
import pytest

from ai_cio.services.mutual_funds.cache import PublicDataCache
from ai_cio.services.mutual_funds.disclosures import (
    import_benchmark, import_disclosure, rows_from_document, validate_benchmark, validate_disclosure,
)
from ai_cio.services.mutual_funds.official_adapters import discover_ppfas, parse_ppfas_portfolio
from ai_cio.services.mutual_funds.provider import (
    AMFI_NAV, MFAPI_CATALOGUE, MutualFundProvider, cache_fingerprint, normalize_nav, parse_amfi,
)

TODAY = date(2026, 10, 20)
ISIN = "INF879O01027"
CATALOGUE = [{"schemeCode": 122639, "schemeName": "Parag Parikh Flexi Cap Fund - Direct Plan - Growth", "isinGrowth": ISIN}]
AMFI = """Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;Scheme Name;Plan;Option;Net Asset Value;Date
Open Ended Schemes(Equity Scheme - Flexi Cap Fund)
PPFAS Mutual Fund
122639;INF879O01027;-;Parag Parikh Flexi Cap Fund;Direct Plan;Growth Option;88.8355;19-Oct-2026
"""


def _provider(tmp_path, handler):
    return MutualFundProvider(cache_dir=tmp_path, transport=httpx.MockTransport(handler))


def test_current_amfi_header_includes_plan_option_without_shifting_nav():
    rows = parse_amfi(AMFI)
    assert rows[0]["current_nav"] == {"date": "2026-10-19", "value": 88.8355}
    assert rows[0]["scheme_name"].endswith("Direct Plan - Growth Option")
    assert rows[0]["isins"] == [ISIN]
    assert rows[0]["fund_house"] == "PPFAS Mutual Fund"
    old = AMFI.replace(";Plan;Option", "").replace(";Direct Plan;Growth Option", "")
    assert parse_amfi(old)[0]["current_nav"]["value"] == 88.8355


def test_no_name_only_or_truncated_isin_identity_substitution(tmp_path):
    p = _provider(tmp_path, lambda request: httpx.Response(200, json=CATALOGUE))
    assert p.resolve({"isin": ISIN, "scheme_name": "Parag Parikh Direct Growth"})["identity_status"] == "verified"
    assert p.resolve({"isin": "INF879O01", "scheme_name": "Parag Parikh Direct Growth"})["identity_status"] == "unresolved"
    assert p.resolve({"scheme_name": "Parag Parikh Direct Growth"})["scheme_code"] is None
    assert p.resolve({"isin": ISIN, "scheme_name": "Parag Parikh Regular Growth"})["identity_status"] == "mismatch"
    assert p.resolve({"isin": ISIN, "scheme_name": "Parag Parikh Direct IDCW"})["identity_status"] == "mismatch"


def test_ambiguous_isin_mapping_is_not_chosen_arbitrarily(tmp_path):
    p = _provider(tmp_path, lambda request: httpx.Response(200, json=CATALOGUE + [{**CATALOGUE[0], "schemeCode": 122640}]))
    assert p.resolve({"isin": ISIN})["identity_status"] == "unresolved"


def test_amfi_catalogue_and_latest_nav_are_independent_fallback_not_history(tmp_path):
    calls = []
    def handler(request):
        calls.append(str(request.url))
        if str(request.url) == AMFI_NAV:
            return httpx.Response(200, text=AMFI)
        return httpx.Response(503)
    p = _provider(tmp_path, handler)
    identity = p.resolve({"isin": ISIN})
    assert identity["identity_status"] == "verified"
    result = p.history(identity, as_of=TODAY)
    assert result["source_url"] == AMFI_NAV
    assert result["history_available"] is False
    assert len(result["points"]) == 1
    assert calls.count(AMFI_NAV) == 1  # same AMFI cached latest/catalogue response


def test_nav_metadata_mismatch_hard_fails_without_silent_fallback(tmp_path):
    def handler(request):
        if str(request.url) == MFAPI_CATALOGUE:
            return httpx.Response(200, json=CATALOGUE)
        assert str(request.url) != AMFI_NAV
        return httpx.Response(200, json={"meta": {"scheme_code": 999999}, "data": [{"date": "19-10-2026", "nav": "100"}]})
    p = _provider(tmp_path, handler)
    result = p.history(p.resolve({"isin": ISIN}), as_of=TODAY)
    assert result["points"] == []
    assert "differs" in result["error"]


def test_nav_dedup_future_invalid_and_conflicting_date_rules():
    rows = [{"date": "19-10-2026", "nav": "100"}, {"date": "19-10-2026", "nav": 100},
            {"date": "21-10-2026", "nav": 110}, {"date": "18-10-2026", "nav": "NaN"}]
    assert normalize_nav(rows, as_of=TODAY) == [{"date": "2026-10-19", "value": 100}]
    with pytest.raises(ValueError, match="Conflicting"):
        normalize_nav(rows + [{"date": "19-10-2026", "nav": 101}], as_of=TODAY)


def test_single_flight_across_different_provider_instances_and_atomic_disk(tmp_path):
    count, lock = 0, threading.Lock()
    def loader():
        nonlocal count
        with lock:
            count += 1
        time.sleep(.02)
        return {"observations": [1, 2, 3]}
    def run(_):
        return PublicDataCache(tmp_path).get("shared", 3600, loader)["payload"]
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(run, range(16)))
    assert count == 1
    assert all(row == {"observations": [1, 2, 3]} for row in results)
    assert len(list(tmp_path.glob("*.json"))) == 1
    assert not list(tmp_path.glob("*.tmp"))


def test_failed_refresh_does_not_replace_old_success_and_stale_bound(tmp_path):
    cache = PublicDataCache(tmp_path)
    cache.write("nav", {"value": 100}, fetched_at=time.time() - 200)
    def fail():
        raise ValueError("offline")
    assert cache.get("nav", 100, fail, max_stale=200)["stale"] is True
    assert cache.read("nav")["payload"] == {"value": 100}
    with pytest.raises(ValueError, match="offline"):
        cache.get("nav", 100, fail, max_stale=10)


def _disclosure(**overrides):
    return {"scheme_code": 122639, "scheme_isin": ISIN, "observed_on": "2026-09-30",
            "source_url": "https://amc.ppfas.com/downloads/portfolio-disclosure/example.xlsx",
            "holdings": [{"isin": "INE040A01034", "name": "HDFC Bank", "weight_pct": 10, "asset_class": "equity"},
                         {"isin": "INE040A01034", "name": "HDFC Bank", "weight_pct": 5, "asset_class": "equity"},
                         {"name": "Cash", "weight_pct": 5}], **overrides}


def _benchmark(**overrides):
    return {"benchmark_id": "NIFTY500TRI", "name": "Nifty 500 TRI", "kind": "TRI",
            "source_url": "https://www.niftyindices.com/reports/historical-data", "observed_on": "2026-10-19",
            "points": [{"date": "2026-10-16", "value": 100}, {"date": "2026-10-19", "value": 101}], **overrides}


def test_disclosure_weights_are_full_nav_not_renormalized_and_duplicates_sum():
    result = validate_disclosure(_disclosure(), as_of=TODAY)
    assert result["coverage_pct"] == 15
    assert result["holdings"][0]["weight_pct"] == 15
    assert result["unidentified_weight_pct"] == 5
    assert result["provenance"] == "user_supplied_source_document"
    assert "not independently" in result["verification"]
    with pytest.raises(ValueError, match="Coverage"):
        validate_disclosure(_disclosure(coverage_pct=100), as_of=TODAY)
    with pytest.raises(ValueError, match="exceed"):
        validate_disclosure(_disclosure(holdings=[{"isin": "INE040A01034", "name": "HDFC", "weight_pct": 90}, {"isin": "INE090A01021", "name": "ICICI", "weight_pct": 20}]), as_of=TODAY)


@pytest.mark.parametrize("url", ["https://www.niftyindices.com.evil.test/x", "http://amc.ppfas.com/x", "https://user:pass@amc.ppfas.com/x", "https://127.0.0.1/x"])
def test_source_host_validation_does_not_accept_lookalike_or_local_urls(url):
    with pytest.raises(ValueError):
        validate_disclosure(_disclosure(source_url=url), as_of=TODAY)


def test_price_benchmark_future_and_conflicting_records_rejected():
    with pytest.raises(ValueError, match="total-return"):
        validate_benchmark(_benchmark(kind="price"), as_of=TODAY)
    with pytest.raises(ValueError, match="Future"):
        validate_benchmark(_benchmark(observed_on="2026-10-21"), as_of=TODAY)
    with pytest.raises(ValueError, match="Conflicting"):
        validate_benchmark(_benchmark(points=[{"date": "2026-10-19", "value": 100}, {"date": "2026-10-19", "value": 101}]), as_of=TODAY)


def test_imports_are_user_scoped_and_fingerprint_does_not_leak_other_imports(tmp_path):
    before = cache_fingerprint(1, cache_dir=tmp_path)
    receipt = import_disclosure(_disclosure(), cache_dir=tmp_path, user_id=2, as_of=TODAY)
    assert receipt["coverage_pct"] == 15
    assert cache_fingerprint(1, cache_dir=tmp_path) == before
    assert cache_fingerprint(2, cache_dir=tmp_path) != before
    p1, p2 = MutualFundProvider(cache_dir=tmp_path, user_id=1, allow_network=False), MutualFundProvider(cache_dir=tmp_path, user_id=2, allow_network=False)
    identity = {"scheme_code": 122639, "isin": ISIN}
    assert p1._import("disclosure", 122639) is None
    assert p2.disclosure(identity, as_of=TODAY)["coverage_pct"] == 15
    import_benchmark(_benchmark(), cache_dir=tmp_path, user_id=2, as_of=TODAY)
    assert p1.benchmark("NIFTY500TRI", as_of=TODAY) is None
    assert p2.benchmark("NIFTY500TRI", as_of=TODAY)["kind"] == "TRI"
    with pytest.raises(ValueError, match="older"):
        import_disclosure(_disclosure(observed_on="2026-08-31"), cache_dir=tmp_path, user_id=2, as_of=TODAY)


def _xlsx(rows, *, formula=False):
    from html import escape
    sheet = []
    for row_index, row in enumerate(rows, 1):
        cells = []
        for col, value in enumerate(row):
            ref = chr(65 + col) + str(row_index)
            if isinstance(value, (int, float)):
                cells.append(f'<c r="{ref}"><v>{value}</v></c>')
            else:
                cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>')
        if formula:
            cells.append(f'<c r="K{row_index}"><f>SUM(A1:A2)</f><v>10</v></c>')
        sheet.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    data = BytesIO()
    with ZipFile(data, "w") as archive:
        archive.writestr("xl/worksheets/sheet1.xml", '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>' + "".join(sheet) + '</sheetData></worksheet>')
    return data.getvalue()


def test_csv_xlsx_normalized_imports_have_same_records_and_no_formulas():
    csv = b"isin,name,weight_pct,asset_class\nINE040A01034,HDFC Bank,10,equity\n"
    rows = [["isin", "name", "weight_pct", "asset_class"], ["INE040A01034", "HDFC Bank", 10, "equity"]]
    expected = [{"isin": "INE040A01034", "name": "HDFC Bank", "weight_pct": "10", "asset_class": "equity"}]
    assert rows_from_document(csv, format="csv") == expected
    assert rows_from_document(_xlsx(rows), format="xlsx") == expected
    with pytest.raises(ValueError, match="Formula"):
        rows_from_document(_xlsx(rows, formula=True), format="xlsx")


def test_ppfas_download_discovery_uses_official_host_past_date_and_exact_scheme():
    html = '<a href="/downloads/portfolio-disclosure/2026/PPFCF_PPFAS_Monthly_Portfolio_Report_September_30_2026.xlsx?1">x</a>'
    html += '<a href="https://evil.test/PPFCF_PPFAS_Monthly_Portfolio_Report_September_30_2026.xlsx">evil</a>'
    html += '<a href="/downloads/portfolio-disclosure/2026/PPFCF_PPFAS_Monthly_Portfolio_Report_October_31_2026.xlsx">future</a>'
    found = discover_ppfas(html, "PPFCF", as_of=TODAY)
    assert len(found) == 1
    assert found[0][0] == date(2026, 9, 30)


def test_ppfas_official_fraction_weights_identity_date_and_hash():
    rows = [["", "Parag Parikh Flexi Cap Fund"], ["", "Monthly Portfolio Statement as on September 30, 2026"],
            ["", "Name of the Instrument", "ISIN", "Industry / Rating", "Quantity", "Market/Fair Value", "% to Net Assets"],
            ["", "Equity & Equity related"], ["", "HDFC Bank", "INE040A01034", "Banks", 10, 1000, .0775],
            ["", "Tiny unknown rounded holding", "INE090A01021", "Banks", 1, 1, "$0.00%"]]
    content = _xlsx(rows)
    identity = {"isin": ISIN, "scheme_code": 122639}
    record = parse_ppfas_portfolio(content, identity, source_url="https://amc.ppfas.com/example.xlsx", observed_on=date(2026, 9, 30), as_of=TODAY)
    assert record["coverage_pct"] == 7.75
    assert record["provenance"] == "official_publisher_fetched"
    assert len(record["sha256"]) == 64
    with pytest.raises(ValueError, match="date"):
        parse_ppfas_portfolio(content, identity, source_url="https://amc.ppfas.com/example.xlsx", observed_on=date(2026, 8, 31), as_of=TODAY)
    rows[0][1] = "Different Scheme Fund"
    with pytest.raises(ValueError, match="title"):
        parse_ppfas_portfolio(_xlsx(rows), identity, source_url="https://amc.ppfas.com/example.xlsx", observed_on=date(2026, 9, 30), as_of=TODAY)


def test_provider_network_budget_expires_before_opening_new_connection(tmp_path):
    calls = []
    p = _provider(tmp_path, lambda request: calls.append(request) or httpx.Response(200, json=[]))
    p._network_deadline = time.monotonic() - 1
    with pytest.raises(ValueError, match="time budget"):
        p._get(MFAPI_CATALOGUE)
    assert calls == []
