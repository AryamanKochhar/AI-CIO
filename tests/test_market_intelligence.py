"""Market intelligence tests — deterministic layers with mocked NSE."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from domain.market.analytics import compute_analytics
from domain.market.contracts import MarketIndexSnapshot
from domain.market.providers.nse import _normalize_heatmap_row
from ai_cio.services.notifications import build_market_observation_email, validate_email_content
from ai_cio.services.opportunity_detection import detect_opportunities

pytestmark = pytest.mark.integration


def _snap(code: str, name: str, chg: str, *, category: str = "sector") -> MarketIndexSnapshot:
    return MarketIndexSnapshot(
        provider="nse",
        index_code=code,
        index_name=name,
        category=category,
        timestamp=datetime.now(timezone.utc),
        current_value=Decimal("100"),
        previous_close=Decimal("103"),
        change=Decimal("-3"),
        change_percent=Decimal(chg),
        day_high=None,
        day_low=None,
        year_high=None,
        year_low=None,
        source="nse",
    )


def test_normalize_heatmap_row():
    row = {
        "index": "NIFTY IT",
        "indexLongName": "Nifty IT",
        "current": 100,
        "close": 103,
        "pChange": -2.91,
        "timeStamp": "31-Aug-2026 15:30:00",
    }
    snap = _normalize_heatmap_row(row, category="sector")
    assert snap is not None
    assert snap.index_code == "NIFTY IT"
    assert snap.change_percent == Decimal("-2.91")


def test_analytics_relative_performance():
    benchmark = _snap("NIFTY 50", "Nifty 50", "-0.8", category="broad")
    it = _snap("NIFTY IT", "IT", "-3.2")
    bank = _snap("NIFTY BANK", "Bank", "0.4")
    analytics = compute_analytics(sectors=[it, bank], benchmark=benchmark)
    it_row = next(r for r in analytics.sectors if r["index_code"] == "NIFTY IT")
    assert it_row["relative_to_benchmark"] == "-2.40"
    assert analytics.breadth["down"] >= 1


def test_opportunity_detection_requires_material_exposure():
    benchmark = _snap("NIFTY 50", "Nifty 50", "-0.8", category="broad")
    it = _snap("NIFTY IT", "IT", "-3.5")
    exposure = {
        "sectors": [
            {
                "sector_index_code": "NIFTY IT",
                "sector_name": "Information Technology",
                "weight_percent": "18.40",
                "value": "240000.00",
            }
        ]
    }
    with patch("ai_cio.services.opportunity_detection.OPPORTUNITY_SECTOR_CHANGE_THRESHOLD", 3.0), patch(
        "ai_cio.services.opportunity_detection.OPPORTUNITY_RELATIVE_CHANGE_THRESHOLD", 2.0
    ), patch("ai_cio.services.opportunity_detection.OPPORTUNITY_EXPOSURE_THRESHOLD_PCT", 5.0):
        candidates = detect_opportunities(
            analytics={"benchmark_change_percent": benchmark.change_percent, "sectors": [], "breadth": {}},
            sector_exposure=exposure,
            snapshots=[it],
        )
    assert len(candidates) == 1
    assert candidates[0].sector_index_code == "NIFTY IT"


def test_email_has_no_forbidden_language():
    subject, body = build_market_observation_email(
        user_name="Aryaman",
        sector_name="Information Technology",
        sector_change="-3.2",
        benchmark_change="-0.8",
        relative_change="-2.4",
        exposure_value="240000",
        exposure_pct="18.4",
        why_surface=["Sector moved materially relative to the broader market."],
        missing=["Mutual fund sector look-through"],
    )
    assert validate_email_content(subject, body) == []
    assert "buy now" not in body.lower()
    assert "not a buy/sell instruction" in body.lower()


def test_twin_includes_market_context(client, db):
    user = client.post("/users", json={"name": "Market"}).json()
    uid = user["id"]
    with patch("ai_cio.services.market_context.get_market_snapshots") as mock_snaps:
        mock_snaps.return_value = [
            _snap("NIFTY 50", "Nifty 50", "-0.8", category="broad"),
            _snap("NIFTY IT", "IT", "-3.2"),
        ]
        twin = client.get(f"/users/{uid}/twin").json()
    assert "market_context" in twin
    assert twin["market_context"]["available"] is True
