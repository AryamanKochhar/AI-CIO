"""CDSL CAS classifier and parser tests using the real fixture PDF."""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from domain.documents import parse_indian_decimal
from domain.documents.cdsl import classify_cdsl_cas, parse_cdsl_cas

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "CDSL.pdf"


pytestmark = pytest.mark.skipif(not FIXTURE.exists(), reason="CDSL.pdf fixture missing")


def test_indian_decimal_parsing():
    assert parse_indian_decimal("1,45,971.00") == Decimal("145971.00")
    assert parse_indian_decimal("(98.75)") == Decimal("-98.75")
    assert parse_indian_decimal("--") is None
    assert parse_indian_decimal("10,26,106.97") == Decimal("1026106.97")


def test_classifier_accepts_cdsl_fixture():
    result = parse_cdsl_cas(FIXTURE)
    ok, matched = classify_cdsl_cas(result.pages)
    assert ok
    assert "Central Depository Services (India) Limited" in matched
    assert "CONSOLIDATED ACCOUNT STATEMENT" in matched


def test_classifier_rejects_unrelated_pdf_text():
    ok, _ = classify_cdsl_cas("This is a random bank statement with no CDSL markers.")
    assert ok is False


def test_cdsl_extracts_statement_metadata():
    result = parse_cdsl_cas(FIXTURE)
    meta = result.metadata
    assert meta.cas_id == "AA13235303"
    assert meta.statement_start == "01-05-2026"
    assert meta.statement_end == "31-05-2026"
    assert meta.total_portfolio_value == Decimal("1257065.12")
    assert meta.equity_value == Decimal("230958.15")
    assert meta.mutual_fund_value == Decimal("1026106.97")


def test_cdsl_extracts_demat_accounts():
    result = parse_cdsl_cas(FIXTURE)
    assert len(result.metadata.demat_accounts) >= 2
    deps = {a.depository for a in result.metadata.demat_accounts}
    assert "CDSL" in deps
    assert "NSDL" in deps


def test_cdsl_extracts_equity_holdings_and_values():
    result = parse_cdsl_cas(FIXTURE)
    equity = [h for h in result.holdings if h.asset_class == "equity" or h.amc == "EQUITY"]
    assert len(equity) == 14
    total = sum((h.valuation or Decimal("0") for h in equity), Decimal("0"))
    assert total == Decimal("230958.15")
    hdfc = next(h for h in equity if h.isin == "INE040A01034")
    assert hdfc.closing_units == Decimal("196.000")
    assert hdfc.valuation == Decimal("145971.00")


def test_cdsl_extracts_equity_transactions():
    result = parse_cdsl_cas(FIXTURE)
    equity_tx = [t for t in result.transactions if t.amc == "EQUITY"]
    assert len(equity_tx) >= 10
    assert any(t.transaction_type == "CREDIT" for t in equity_tx)
    assert any(t.transaction_type == "DEBIT" for t in equity_tx)
    assert any("EP-DR" in t.description or "PAYOUT" in t.description for t in equity_tx)


def test_cdsl_extracts_mf_holdings_with_pl():
    result = parse_cdsl_cas(FIXTURE)
    mf = [h for h in result.holdings if h.asset_class == "mutual_fund"]
    assert len(mf) == 12
    total = sum((h.valuation or Decimal("0") for h in mf), Decimal("0"))
    assert total == Decimal("1026106.97")
    assert all(h.invested_amount is not None for h in mf)
    assert any(h.unrealised_pl is not None for h in mf)


def test_cdsl_extracts_mf_transactions():
    result = parse_cdsl_cas(FIXTURE)
    mf_tx = [t for t in result.transactions if t.amc != "EQUITY"]
    assert len(mf_tx) >= 10
    assert any(t.amount == Decimal("999.95") for t in mf_tx)


def test_cdsl_extracts_portfolio_snapshots():
    result = parse_cdsl_cas(FIXTURE)
    assert len(result.metadata.snapshots) == 12
    assert result.metadata.snapshots[-1].month_year == "May 2026"
    assert result.metadata.snapshots[-1].valuation == Decimal("1257065.12")
