"""Publisher layout/identity boundaries, using small original synthetic fixtures."""
from datetime import date
from html import escape
from io import BytesIO
import json
from zipfile import ZipFile

import httpx
import pytest

from ai_cio.services.mutual_funds.catalogued_disclosures import (
    NIPPON_INDEX, PGIM_LISTING, discover_nippon, discover_pgim, parse_catalogued_portfolio,
)
from ai_cio.services.mutual_funds.disclosures import _xlsx_rows, rows_from_document
from ai_cio.services.mutual_funds.nippon_published import discover_nippon_factsheets, parse_nippon_published
from ai_cio.services.mutual_funds.provider import MutualFundProvider

TODAY = date(2026, 10, 20)
OBSERVED = date(2026, 9, 30)
NIPPON_URL = "https://mf.nipponindiaim.com/InvestorServices/FactsheetsDocuments/NIMF-MONTHLY-PORTFOLIO-30-Sep-26.xls"
PGIM_URL = "https://www.pgimindia.com/api/v1/brochure/about-us/image/PGIM INDIA MIDCAP FUND Sep 2026.xlsx"
PUBLISHED_URL = "https://mf.nipponindiaim.com/InvestorServices/FactsheetsDocuments/Fundamentals-September-2026/Innerpage/Small-Cap.html"
NIPPON = {"isin": "INF204K01K15", "scheme_code": 118778, "identity_status": "verified", "plan": "direct", "option": "growth"}
PGIM = {"isin": "INF663L01DV3", "scheme_code": 125307, "identity_status": "verified", "plan": "direct", "option": "growth"}


def workbook(rows, sheet="SC", *, extra_sheet=False, external=False, empty_inline=False):
    cells = []
    for i, row in enumerate(rows, 1):
        columns = []
        for j, value in enumerate(row):
            ref = chr(65 + j) + str(i)
            if isinstance(value, (int, float)):
                columns.append(f'<c r="{ref}"><v>{value}</v></c>')
            else:
                columns.append(f'<c r="{ref}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>')
        if empty_inline:
            columns.append(f'<c r="Z{i}" t="inlineStr"/>')
        cells.append(f'<row r="{i}">{"".join(columns)}</row>')
    out = BytesIO()
    with ZipFile(out, "w") as z:
        z.writestr("xl/workbook.xml", '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheets>'
                   + f'<sheet xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" name="{sheet}" r:id="rId7"/>'
                   + ('<sheet name="Other"/>' if extra_sheet else '') + '</sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   + f'<Relationship Id="rId7" Target="/xl/worksheets/sheet7.xml"'+(' TargetMode="External"' if external else '')+'/></Relationships>')
        z.writestr("xl/worksheets/sheet7.xml", '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
                   + ''.join(cells) + '</sheetData></worksheet>')
        if extra_sheet:
            z.writestr("xl/worksheets/sheet1.xml", '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"/>')
    return out.getvalue()


def portfolio_rows(publisher="nippon", *, weight=None):
    if publisher == "nippon":
        return [["RLMF200", "NIPPON INDIA SMALL CAP FUND"], ["", "Monthly Portfolio Statement as on September 30,2026"],
                ["", "ISIN", "Name of the Instrument", "Industry / Rating", "Quantity", "Market/Fair Value", "% to NAV"],
                ["", "", "Equity & Equity related"],
                ["", "INE040A01034", "Example Bank", "Banks", 100, 1000, .075 if weight is None else weight],
                ["", "", "Triparty Repo", "", "", 500, .02], ["BENCHMARK NAME - NIFTY SMALLCAP 250 TRI"]]
    return [["", "PGIM INDIA MIDCAP FUND"], ["", "Portfolio Statement as on September 30,2026"],
            ["", "Name of  Instrument", "ISIN", "Industry/Rating", "Quantity", "Market/Fair Value", "%  to Net Assets"],
            ["", "Equity & Equity related"],
            ["", "Example Bank", "INE040A01034", "Banks", 100, 1000, 7.5 if weight is None else weight],
            ["Riskometer of the Benchmark (Nifty Midcap 150 TRI)"]]


def parse(publisher="nippon", *, rows=None, **kwargs):
    return parse_catalogued_portfolio(workbook(rows or portfolio_rows(publisher), "SC" if publisher == "nippon" else "Mid Cap"),
                                      NIPPON if publisher == "nippon" else PGIM,
                                      source_url=NIPPON_URL if publisher == "nippon" else PGIM_URL,
                                      observed_on=OBSERVED, as_of=TODAY, **kwargs)


def test_exact_named_sheet_uses_relationship_and_uploads_still_require_single_sheet():
    blob = workbook([["hello"]], extra_sheet=True, empty_inline=True)
    assert _xlsx_rows(blob, sheet_name="SC")[0][0] == "hello"
    assert _xlsx_rows(blob, sheet_name="SC")[0][-1] == ""
    with pytest.raises(ValueError, match="single-sheet"):
        rows_from_document(blob, format="xlsx")
    with pytest.raises(ValueError, match="unique configured"):
        _xlsx_rows(blob, sheet_name="Missing")
    with pytest.raises(ValueError, match="relationship"):
        _xlsx_rows(workbook([["x"]], external=True), sheet_name="SC")


def test_two_publishers_units_produce_same_full_nav_weight_without_renormalization():
    for publisher in ("nippon", "pgim"):
        result = parse(publisher)
        assert result["coverage_pct"] == 7.5
        assert result["holdings"][0]["weight_pct"] == 7.5
        assert result["holdings"][0]["asset_class"] == "equity"
        assert result["provenance"] == "official_publisher_fetched"
        assert result["ter_percent"] is None
        assert result["benchmark_id"].endswith("TRI")


@pytest.mark.parametrize("publisher", ["nippon", "pgim"])
@pytest.mark.parametrize("mutation", ["title", "date", "header", "benchmark"])
def test_changed_publisher_layout_or_identity_fails_closed(publisher, mutation):
    rows = portfolio_rows(publisher)
    if mutation == "title": rows[0][1] = "DIFFERENT FUND"
    elif mutation == "date": rows[1][1] = "Portfolio Statement as on August 31,2026"
    elif mutation == "header": rows[2][-1] = "Market Value"
    else: rows[-1] = ["Benchmark price index only"]
    with pytest.raises(ValueError):
        parse(publisher, rows=rows)


def test_nippon_percentage_layout_change_and_gross_exposure_do_not_pass_silently():
    with pytest.raises(ValueError, match="outside"):
        parse("nippon", rows=portfolio_rows(weight=7.5))
    rows = portfolio_rows("pgim", weight=90)
    rows.insert(5, ["", "Other Bank", "INE090A01021", "Banks", 100, 100, 20])
    with pytest.raises(ValueError, match="exceed"):
        parse("pgim", rows=rows)


def listing_item(**overrides):
    return {"title": "PGIM INDIA MIDCAP FUND Sep 2026", "dateMonthYear": "30 September 2026", "pdfPath": PGIM_URL,
            "displayStatus": True, "disclosureTab": 12, **overrides}


def listing(*items):
    return {"data": [{"tabId": 12, "tabName": "Equity", "content": list(items)}]}


def test_discovery_rejects_future_wrong_scheme_and_off_host_downloads():
    html = f'<a href="{NIPPON_URL}">ok</a>' + f'<a href="{NIPPON_URL.replace("mf.nipponindiaim.com", "evil.test")}">bad</a>'
    html += f'<a href="{NIPPON_URL.replace("30-Sep", "31-Oct")}">future</a>'
    assert discover_nippon(html, as_of=TODAY) == [(OBSERVED, NIPPON_URL)]
    good = listing_item()
    for bad in (listing_item(title="PGIM INDIA LARGE AND MIDCAP FUND Sep 2026"),
                listing_item(pdfPath=PGIM_URL.replace("www.pgimindia.com", "evil.test")),
                listing_item(dateMonthYear="31 August 2026"), listing_item(displayStatus=False),
                listing_item(pdfPath=PGIM_URL + "?redirect=evil")):
        assert discover_pgim(listing(bad), as_of=TODAY) == []
    assert discover_pgim(listing(good), as_of=TODAY) == [(OBSERVED, PGIM_URL)]


def test_provider_fetches_only_configured_public_read_form_and_caches_workbook(tmp_path):
    calls = []
    blob = workbook(portfolio_rows("pgim"), "Mid Cap")
    def handler(request):
        calls.append((request.method, str(request.url)))
        if str(request.url) == PGIM_LISTING:
            assert request.method == "POST"
            assert json.loads(request.content) == {"sectionId": "SECTION_747960037", "tabId": 12}
            return httpx.Response(200, json=listing(listing_item()))
        assert request.method == "GET" and str(request.url) == PGIM_URL.replace(" ", "%20")
        return httpx.Response(200, content=blob)
    provider = MutualFundProvider(cache_dir=tmp_path, transport=httpx.MockTransport(handler))
    first = provider.disclosure(PGIM, as_of=TODAY)
    assert first["coverage_pct"] == 7.5
    assert provider.disclosure(PGIM, as_of=TODAY)["sha256"] == first["sha256"]
    assert len(calls) == 2
    assert provider.disclosure({**PGIM, "plan": "regular"}, as_of=TODAY) is None


def factsheet():
    return '''<title>Nippon India Small Cap Fund</title><table><tr><td>Benchmark Name:</td><td>Nifty Smallcap 250 TRI</td></tr></table>
<table><tr><td>Compounded Annualised Returns</td><td>Scheme Returns % - Regular</td><td>Scheme Returns % - Direct</td><td>Benchmark Returns %</td></tr>
<tr><td>Returns for last 1 year</td><td>9.2</td><td>10.2</td><td>8.1</td></tr>
<tr><td>Returns for last 3 years</td><td>11.3</td><td>12.3</td><td>11.2</td></tr>
<tr><td>Returns for last 5 years</td><td>12.4</td><td>13.4</td><td>12.3</td></tr></table>
<p>Performance as on August 31, 2026.</p><p>Direct expense ratio (BER) 0.60%</p>'''


def test_published_returns_keep_actual_date_and_plan_separate_from_option_and_tri_history():
    result = parse_nippon_published(factsheet(), NIPPON, source_url=PUBLISHED_URL, as_of=TODAY)
    assert result["observed_on"] == "2026-08-31"  # not the September folder date
    assert result["returns"][0]["fund_return_pct"] == 10.2
    assert result["returns"][0]["excess_return_pp"] == 2.1
    assert result["option_verified"] is False
    assert result["benchmark_history"] == [] and result["rolling"] is None
    assert "ter_percent" not in result
    index = PUBLISHED_URL.replace("Innerpage/Small-Cap.html", "index.html")
    assert discover_nippon_factsheets(f'<a href="{index}">x</a>', as_of=TODAY)[0][1] == PUBLISHED_URL


@pytest.mark.parametrize("old,new", [("Small Cap Fund</title>", "Large Cap Fund</title>"),
                                       ("August 31, 2026", "October 31, 2026"),
                                       ("Nifty Smallcap 250 TRI", "Nifty Smallcap 250 Price"),
                                       ("10.2</td>", "NaN</td>"),
                                       ("Scheme Returns % - Direct", "SIP Direct Return")])
def test_published_comparison_rejects_identity_date_schema_and_nonfinite_cells(old, new):
    with pytest.raises(ValueError):
        parse_nippon_published(factsheet().replace(old, new), NIPPON, source_url=PUBLISHED_URL, as_of=TODAY)
