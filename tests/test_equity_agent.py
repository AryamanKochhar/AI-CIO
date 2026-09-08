"""Unit tests for equity agent helpers (no live OpenRouter calls)."""
from domain.decision.contracts import DecisionObjective
from ai_cio.services.agents.equity_agent import _equity_payload
from ai_cio.services.agents.openrouter_client import extract_json_object


def test_extract_json_object_from_fence():
    text = """```json
{"decision": "Review concentration", "observations": ["A"], "recommended_actions": ["B"]}
```"""
    data = extract_json_object(text)
    assert data["decision"] == "Review concentration"
    assert data["recommended_actions"] == ["B"]


def test_equity_payload_filters_direct_equity():
    twin = {
        "user": {"id": 1, "name": "A"},
        "behaviour": {"status": "known"},
        "goals": {"items": []},
        "financial_position": {},
        "completeness": {"portfolio": True},
        "portfolio": {
            "holdings": [
                {"scheme_name": "HDFC BANK", "amc": "EQUITY", "asset_class": "equity", "valuation": "10"},
                {"scheme_name": "Debt Fund", "amc": "X", "asset_class": "mutual_fund", "valuation": "5"},
                {
                    "scheme_name": "Nifty Index Fund",
                    "amc": "Y",
                    "asset_class": "mutual_fund",
                    "valuation": "7",
                },
            ]
        },
    }
    pre = {
        "holding_metrics": [
            {"instrument_type": "direct_equity", "name": "HDFC BANK", "portfolio_weight_percent": "50"},
            {"instrument_type": "mutual_fund", "name": "Debt Fund", "portfolio_weight_percent": "25"},
        ],
        "portfolio_flags": {"missing_goals": True},
    }
    payload = _equity_payload(twin, pre)
    assert payload["equity_sleeve"]["counts"]["direct_equity"] == 1
    assert payload["equity_sleeve"]["counts"]["equity_oriented_funds"] == 1
    assert len(payload["preanalysis"]["holding_metrics"]) == 1
    assert DecisionObjective.REVIEW_EQUITY_PORTFOLIO.value == "review_equity_portfolio"
