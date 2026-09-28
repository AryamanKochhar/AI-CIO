"""Tax rule engine, lots, and intelligence tests."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from ai_cio.services.tax.engine import build_tax_intelligence
from ai_cio.services.tax.lots import build_tax_lots
from ai_cio.services.tax.rules import (
    classify_asset,
    estimate_equity_tax,
    fy_bounds,
    get_rules,
    holding_classification,
)
from ai_cio.services.agents.tax_agent import tax_impact_for_actions


def test_fy_bounds_and_rules_version():
    rules = get_rules("2025-26")
    assert rules.version == "fy2025-26.v1"
    start, end = fy_bounds("2025-26")
    assert start == date(2025, 4, 1)
    assert end == date(2026, 3, 31)


def test_holding_period_boundary_equity():
    rules = get_rules()
    st = holding_classification(
        category="listed_equity",
        acquisition=date(2025, 6, 1),
        disposal_or_as_of=date(2026, 5, 31),
        rules=rules,
    )
    assert st["status"] == "ok"
    assert st["term"] == "short_term"
    assert st["days_to_long_term"] == 1

    lt = holding_classification(
        category="listed_equity",
        acquisition=date(2025, 6, 1),
        disposal_or_as_of=date(2026, 6, 1),
        rules=rules,
    )
    assert lt["term"] == "long_term"
    assert lt["days_to_long_term"] == 0


def test_missing_acquisition_date_insufficient():
    rules = get_rules()
    row = holding_classification(
        category="listed_equity",
        acquisition=None,
        disposal_or_as_of=date(2026, 1, 1),
        rules=rules,
    )
    assert row["status"] == "insufficient_data"
    assert row["term"] is None


def test_stcg_ltcg_and_loss_setoff_estimate():
    rules = get_rules()
    est = estimate_equity_tax(
        stcg=Decimal("100000"),
        ltcg=Decimal("200000"),
        stcl=Decimal("40000"),
        ltcl=Decimal("10000"),
        rules=rules,
    )
    # STCL offsets STCG first → taxable STCG 60k @ 20% = 12k
    assert est["taxable_stcg"] == "60000.00"
    # LTCG 200k - 10k LTCL = 190k; exemption 125k → 65k @ 12.5%
    assert est["taxable_ltcg_after_exemption"] == "65000.00"
    assert est["estimated_stcg_tax"] == "12000.00"
    assert est["estimated_ltcg_tax"] == "8125.00"
    assert est["estimated_capital_gains_tax"] == "20125.00"
    assert est["rule_version"] == rules.version


def test_fifo_realized_stcg_and_ltcg():
    holdings = []
    transactions = [
        {
            "isin": "INF000TEST01",
            "scheme_name": "Test Equity Fund",
            "amc": "AMC",
            "date": "2024-01-10",
            "transaction_type": "PURCHASE",
            "units": "100",
            "nav": "100",
            "amount": "10000",
        },
        {
            "isin": "INF000TEST01",
            "scheme_name": "Test Equity Fund",
            "amc": "AMC",
            "date": "2025-06-15",
            "transaction_type": "PURCHASE",
            "units": "50",
            "nav": "120",
            "amount": "6000",
        },
        {
            "isin": "INF000TEST01",
            "scheme_name": "Test Equity Fund",
            "amc": "AMC",
            "date": "2025-08-01",
            "transaction_type": "REDEEM",
            "units": "80",
            "nav": "150",
            "amount": "12000",
        },
    ]
    lots = build_tax_lots(holdings, transactions, as_of=date(2026, 3, 1), financial_year="2025-26")
    assert len(lots["realized_lots"]) >= 1
    # FIFO: first 80 from Jan-2024 lot → long-term (purchase > 365 days before sale)
    first = lots["realized_lots"][0]
    assert first["term"] == "long_term"
    assert Decimal(first["gain_loss"]) == Decimal("4000.00")  # (150-100)*80


def test_missing_acquisition_price_on_equity_txn():
    holdings = [
        {
            "isin": "INE002A01018",
            "scheme_name": "RELIANCE",
            "amc": "EQUITY",
            "asset_class": "equity",
            "closing_units": "10",
            "nav": "1400",
            "valuation": "14000",
        }
    ]
    transactions = [
        {
            "isin": "INE002A01018",
            "scheme_name": "RELIANCE",
            "amc": "EQUITY",
            "date": "2025-01-10",
            "transaction_type": "CREDIT",
            "units": "10",
            "nav": None,
            "amount": "5",  # stamp duty only — ignored for equity_like
        }
    ]
    payload = build_tax_intelligence(holdings, transactions, financial_year="2025-26", as_of=date(2026, 3, 1))
    assert any(m.get("reason") == "missing_acquisition_cost" for m in payload["missing_data"])
    assert payload["summary"]["unrealized_gains"] == "0.00"
    assert payload["status"] == "insufficient_data"
    assert payload["data_quality"]["coverage_pct"] == 0
    # Must not invent a tax liability from guessed cost basis
    assert payload["summary"]["estimated_tax"] == "0.00"


def test_tax_loss_harvesting_and_holding_period_opportunity():
    as_of = date(2026, 3, 1)
    holdings = [
        {
            "isin": "INFLOSS00001",
            "scheme_name": "Loss Fund",
            "amc": "AMC",
            "asset_class": "mutual_fund",
            "closing_units": "100",
            "nav": "80",
            "valuation": "8000",
            "invested_amount": None,
        },
        {
            "isin": "INFNEARLT001",
            "scheme_name": "Near LT Fund",
            "amc": "AMC",
            "asset_class": "mutual_fund",
            "closing_units": "50",
            "nav": "200",
            "valuation": "10000",
        },
    ]
    transactions = [
        {
            "isin": "INFLOSS00001",
            "scheme_name": "Loss Fund",
            "amc": "AMC",
            "date": "2025-04-10",
            "transaction_type": "PURCHASE",
            "units": "100",
            "nav": "120",
            "amount": "12000",
        },
        {
            "isin": "INFNEARLT001",
            "scheme_name": "Near LT Fund",
            "amc": "AMC",
            "date": "2025-04-10",  # ~325 days to as_of → still ST, days_to_lt ~40
            "transaction_type": "PURCHASE",
            "units": "50",
            "nav": "150",
            "amount": "7500",
        },
        {
            "isin": "INFGAIN00001",
            "scheme_name": "Sold Fund",
            "amc": "AMC",
            "date": "2025-05-01",
            "transaction_type": "PURCHASE",
            "units": "20",
            "nav": "100",
            "amount": "2000",
        },
        {
            "isin": "INFGAIN00001",
            "scheme_name": "Sold Fund",
            "amc": "AMC",
            "date": "2025-07-01",
            "transaction_type": "REDEEM",
            "units": "20",
            "nav": "200",
            "amount": "4000",
        },
    ]
    payload = build_tax_intelligence(holdings, transactions, financial_year="2025-26", as_of=as_of)
    assert Decimal(payload["summary"]["stcg"]) == Decimal("2000.00")
    tlh = [o for o in payload["opportunities"] if o["type"] == "tax_loss_harvesting"]
    assert tlh
    assert "Potential tax-loss harvesting" in tlh[0]["reason"]
    assert any(e["security"] == "Near LT Fund" for e in payload["holding_period_events"])
    assert any("STCG" in c for c in payload["comments"])
    assert payload["loss_inventory"]["carry_forward_history"] == "unavailable"
    assert any(a["type"] == "tax_loss_harvesting" for a in payload["alerts"])


def test_gain_harvesting_headroom():
    as_of = date(2026, 3, 1)
    holdings = [
        {
            "isin": "INFLTGAIN001",
            "scheme_name": "LT Gain Fund",
            "amc": "AMC",
            "asset_class": "mutual_fund",
            "closing_units": "100",
            "nav": "200",
            "valuation": "20000",
        }
    ]
    transactions = [
        {
            "isin": "INFLTGAIN001",
            "scheme_name": "LT Gain Fund",
            "amc": "AMC",
            "date": "2024-01-01",
            "transaction_type": "PURCHASE",
            "units": "100",
            "nav": "100",
            "amount": "10000",
        }
    ]
    payload = build_tax_intelligence(holdings, transactions, financial_year="2025-26", as_of=as_of)
    gh = [o for o in payload["opportunities"] if o["type"] == "gain_harvesting"]
    assert gh
    assert Decimal(gh[0]["amount"]) > 0
    assert "gain-harvesting" in gh[0]["reason"].lower()


def test_duplicate_transactions_still_fifo():
    holdings = [
        {
            "isin": "INFDUPE00001",
            "scheme_name": "Dupe Fund",
            "amc": "AMC",
            "asset_class": "mutual_fund",
            "closing_units": "5",
            "nav": "110",
            "valuation": "550",
        }
    ]
    transactions = [
        {
            "isin": "INFDUPE00001",
            "scheme_name": "Dupe Fund",
            "amc": "AMC",
            "date": "2025-04-01",
            "transaction_type": "PURCHASE",
            "units": "10",
            "nav": "100",
            "amount": "1000",
        },
        {
            "isin": "INFDUPE00001",
            "scheme_name": "Dupe Fund",
            "amc": "AMC",
            "date": "2025-04-01",
            "transaction_type": "PURCHASE",
            "units": "10",
            "nav": "100",
            "amount": "1000",
        },
        {
            "isin": "INFDUPE00001",
            "scheme_name": "Dupe Fund",
            "amc": "AMC",
            "date": "2025-09-01",
            "transaction_type": "REDEEM",
            "units": "15",
            "nav": "110",
            "amount": "1650",
        },
    ]
    lots = build_tax_lots(holdings, transactions, as_of=date(2026, 3, 1), financial_year="2025-26")
    assert sum(Decimal(r["qty"]) for r in lots["realized_lots"]) == Decimal("15.0000")
    open_qty = sum(Decimal(r["qty"]) for r in lots["unrealized_lots"])
    assert open_qty == Decimal("5.0000")


def test_tax_impact_for_actions_includes_sell_caution():
    tax_payload = {
        "available": True,
        "summary": {"stcg": "1000.00", "ltcg": "0.00", "estimated_tax": "200.00"},
        "opportunities": [
            {
                "type": "tax_loss_harvesting",
                "label": "Potential tax-loss harvesting opportunity",
                "reason": "example",
                "estimated_tax_impact": "50.00",
                "risks": ["re-entry"],
            }
        ],
        "missing_data": [],
    }
    rows = tax_impact_for_actions(tax_payload, ["Rebalance / sell Fund A", "Hold cash"])
    assert any(r.get("label") == "TAX IMPACT (current year position)" for r in rows)
    assert any("Recommendation tax caution" in str(r.get("label")) for r in rows)


def test_classify_asset_debt_vs_equity():
    assert classify_asset(asset_class="equity", scheme_name="RELIANCE", amc="EQUITY") == "listed_equity"
    assert classify_asset(asset_class="mutual_fund", scheme_name="Liquid Fund", amc="X") == "debt_oriented_mf"
    assert classify_asset(asset_class="mutual_fund", scheme_name="Flexi Cap Growth", amc="X") == "equity_oriented_mf"


def test_coordinator_invokes_tax_agent(monkeypatch):
    """Tax Agent is a first-class orchestrator stage and appears on DecisionResult."""
    from types import SimpleNamespace

    from domain.decision.contracts import (
        AnalysisResult,
        DecisionObjective,
        DecisionRequest,
        InvestmentStrategy,
    )
    from ai_cio.services.orchestration import coordinator as coord

    tax_calls: list[int] = []

    def fake_tax(db, user_id, financial_year=None):
        tax_calls.append(user_id)
        return {
            "available": True,
            "agent": "tax_agent",
            "status": "success",
            "rule_version": "fy2025-26.v1",
            "financial_year": "2025-26",
            "summary": {
                "stcg": "1000.00",
                "ltcg": "0.00",
                "stcl": "0.00",
                "ltcl": "0.00",
                "estimated_tax": "200.00",
            },
            "opportunities": [
                {
                    "type": "tax_loss_harvesting",
                    "label": "Potential tax-loss harvesting opportunity",
                    "reason": "Potential tax-loss harvesting opportunity",
                    "estimated_tax_impact": "50.00",
                    "risks": [],
                }
            ],
            "comments": ["You have ₹1000 of realized STCG this financial year (from available transactions)."],
            "missing_data": [],
            "alerts": [],
        }

    class StubTwin:
        def load_twin(self, user_id: int):
            return {
                "user": {"id": user_id, "name": "Tax User"},
                "behaviour": {"status": "unknown"},
                "goals": {"items": []},
                "financial_position": {
                    "income": {"value": None, "known": False},
                    "expenses": {"value": None, "known": False},
                    "liquid": {"value": None, "known": False},
                },
                "portfolio": {"holdings": [], "total_value": {"value": "0", "known": True}},
                "completeness": {
                    "behaviour": False,
                    "goals": False,
                    "finances": False,
                    "portfolio": True,
                    "documents": True,
                },
                "ready_for_analysis": True,
                "preanalysis": {},
            }

    class StubMarket:
        def load_market_context(self, user_id: int):
            return {"available": False}

    class StubKnowledge:
        def resolve(self, *, objective, topics):
            return []

    class StubAnalyzer:
        name = "stub"

        def analyze(self, context, capabilities=None):
            strategy = InvestmentStrategy(
                name="Balanced",
                allocation={"equity": Decimal("60"), "debt": Decimal("40")},
                rationale=["stub"],
                assumptions=[],
                expected_characteristics={"confidence": "low"},
                risks=[],
            )
            return AnalysisResult(
                observations=["stub observation"],
                candidate_strategies=[strategy],
                risks=[],
                tradeoffs=[],
                assumptions=[],
                evidence=[],
                missing_information=[],
                decision_summary="Review portfolio with tax context.",
                recommended_actions=["Rebalance / sell concentrated fund"],
            )

    monkeypatch.setattr(coord, "SessionTwinProvider", lambda db: StubTwin())
    monkeypatch.setattr(coord, "SessionMarketProvider", lambda db: StubMarket())
    monkeypatch.setattr(coord, "SessionKnowledgeProvider", lambda: StubKnowledge())
    monkeypatch.setattr(coord, "run_tax_agent", fake_tax)
    monkeypatch.setattr(coord, "build_sector_opportunity", lambda *a, **k: {"available": False})
    monkeypatch.setattr(coord, "build_decision_suggestions", lambda **k: {"available": False, "items": []})
    monkeypatch.setattr(coord.settings, "TAX_INTELLIGENCE_ENABLED", True)
    monkeypatch.setattr(coord.settings, "SECTOR_OPPORTUNITY_ENABLED", False)
    monkeypatch.setattr(coord.settings, "EQUITY_AGENT_ENABLED", False)

    request = DecisionRequest.from_payload(
        user_id=42,
        objective=DecisionObjective.REVIEW_PORTFOLIO.value,
    )
    result = coord.run_decision(SimpleNamespace(), request, analyzer=StubAnalyzer())

    assert tax_calls == [42]
    assert "tax_agent" in (result.get("execution") or {}).get("stages", [])
    tax = result.get("tax_intelligence") or {}
    assert tax.get("available") is True
    assert tax.get("summary", {}).get("stcg") == "1000.00"
    assert tax.get("tax_implications_for_recommendations")
    assert any("TAX IMPACT" in str(r.get("label", "")) for r in tax["tax_implications_for_recommendations"])
    assert "tax_analysis" in (result.get("execution") or {}).get("capabilities", [])
