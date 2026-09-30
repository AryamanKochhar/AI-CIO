"""Tests for Trendlyne sector day-change parsing."""
from __future__ import annotations

from unittest.mock import patch

from ai_cio.services.trendlyne_sectors import _parse_sectors, fetch_sector_day_changes
import ai_cio.services.trendlyne_sectors as mod


def test_parse_sectors_uses_signed_param_value():
    payload = {
        "body": {
            "sector": {
                "chart": [
                    {"name": "Healthcare", "value": 3.21, "param_value": -3.21, "disp_value": "-3.21%"},
                    {"name": "Media", "value": 3.02, "param_value": 3.02, "disp_value": "3.02%"},
                ]
            }
        }
    }
    rows = _parse_sectors(payload)
    assert rows[0]["name"] == "Media"
    assert rows[0]["day_change_percent"] == 3.02
    assert rows[1]["name"] == "Healthcare"
    assert rows[1]["day_change_percent"] == -3.21


def test_fetch_sector_day_changes_builds_well_and_poor():
    mod._cache = None
    mod._cache_at = 0.0
    fake = {
        "body": {
            "sector": {
                "chart": [
                    {"name": "A", "param_value": 2.5, "disp_value": "2.5%"},
                    {"name": "B", "param_value": -1.2, "disp_value": "-1.2%"},
                    {"name": "C", "param_value": 0.4, "disp_value": "0.4%"},
                ]
            }
        }
    }

    class FakeResp:
        def raise_for_status(self):
            return None

        def json(self):
            return fake

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, *a, **k):
            return FakeResp()

    with patch("ai_cio.services.trendlyne_sectors.httpx.Client", FakeClient):
        with patch("ai_cio.services.trendlyne_sectors._enabled", return_value=True):
            out = fetch_sector_day_changes(force=True)

    assert out["available"] is True
    assert out["doing_well"][0]["name"] == "A"
    assert out["doing_poorly"][0]["name"] == "B"
