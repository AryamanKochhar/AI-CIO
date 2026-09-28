"""FD rate parser + intelligence tests (no live network required)."""
from __future__ import annotations

from decimal import Decimal

from ai_cio.services.fd.rates import match_bank_rate, parse_fd_rate_tables
from ai_cio.services.agents.fd_agent import fd_impact_for_actions


SAMPLE_HTML = """
<html><body>
<table>
<tr><th>Bank</th><th>Interest Rates for General Public (p.a)</th><th>Interest Rates for Senior Citizens (p.a)</th></tr>
<tr><td>HDFC Bank</td><td>2.75% - 6.50%</td><td>3.25% - 7.00%</td></tr>
<tr><td>State Bank of India</td><td>3.05% - 6.45%</td><td>3.55% - 7.05%</td></tr>
<tr><td>IDFC FIRST Bank</td><td>3.50% - 7.40%</td><td>4.00% - 7.90%</td></tr>
</table>
</body></html>
"""


def test_parse_fd_rate_tables():
    rows = parse_fd_rate_tables(SAMPLE_HTML)
    assert len(rows) == 3
    hdfc = next(r for r in rows if r["bank"] == "HDFC Bank")
    assert hdfc["general_min"] == "2.75"
    assert hdfc["general_max"] == "6.50"
    assert hdfc["senior_max"] == "7.00"


def test_match_bank_rate_fuzzy():
    rows = parse_fd_rate_tables(SAMPLE_HTML)
    assert match_bank_rate("HDFC", rows)["bank"] == "HDFC Bank"
    assert match_bank_rate("SBI", rows) is None or match_bank_rate("State Bank", rows)["bank"] == "State Bank of India"


def test_fd_impact_for_actions():
    payload = {
        "available": True,
        "summary": {"fd_count": 1, "total_principal": "100000.00", "liquid_cash": "50000.00"},
        "maturity_alerts": [{"reason": "Matures soon"}],
        "opportunities": [{"type": "idle_cash", "reason": "Cash buffer note"}],
    }
    rows = fd_impact_for_actions(payload, ["Raise liquid buffer", "Rebalance equity"])
    assert any("FD / CASH" in str(r.get("label")) for r in rows)
    assert any("Liquidity" in str(r.get("label")) for r in rows)


def test_build_fd_intelligence_with_user_fds(monkeypatch):
    from ai_cio.services.fd import holdings as holdings_mod

    monkeypatch.setattr(
        holdings_mod,
        "list_fixed_deposits",
        lambda db, user_id: [
            {
                "id": 1,
                "bank_name": "HDFC Bank",
                "account_label": "Primary",
                "principal": "200000.00",
                "interest_rate_pa": "6.00",
                "tenure_months": 12,
                "start_date": None,
                "maturity_date": None,
                "compounding": "cumulative",
                "is_senior_citizen": False,
                "notes": None,
            }
        ],
    )
    monkeypatch.setattr(
        holdings_mod,
        "get_fd_rates",
        lambda db, force_refresh=False: {
            "source": "test",
            "source_url": "https://example.com",
            "status": "live",
            "rates": [
                {
                    "bank": "HDFC Bank",
                    "general_min": "2.75",
                    "general_max": "6.50",
                    "senior_min": "3.25",
                    "senior_max": "7.00",
                }
            ],
        },
    )
    payload = holdings_mod.build_fd_intelligence(None, 1, liquid=Decimal("75000"))
    assert payload["available"] is True
    assert payload["summary"]["fd_count"] == 1
    assert payload["summary"]["total_principal"] == "200000.00"
    assert any("fixed deposit" in c.lower() for c in payload["comments"])
    assert payload["fixed_deposits"][0]["rate_gap_pa"] == "0.50"
