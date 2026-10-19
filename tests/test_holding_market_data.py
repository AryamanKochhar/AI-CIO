from datetime import datetime, timedelta
import json

import pytest

from ai_cio.services import holding_market_data as market
from ai_cio.services.sector_opportunity import _rsi


def candles():
    today = datetime.now(market.IST).date()
    days = []
    for ago in range(150, 0, -1):
        day = today - timedelta(days=ago)
        if day.weekday() < 5:
            days.append(datetime.combine(day, datetime.min.time(), tzinfo=market.IST).timestamp())
    return {"timestamp": days, "close": [100+i for i in range(len(days))], "volume": [1000]*len(days)}


def test_validation_sorts_completed_candles_and_removes_unfinished_session():
    now = datetime(2026, 10, 20, 10, tzinfo=market.IST)
    stamps = [datetime(2026,10,20,tzinfo=market.IST).timestamp(), datetime(2026,10,19,tzinfo=market.IST).timestamp()]
    result = market.validate_history({"timestamp": stamps, "close": [130,120], "volume": [50,100]}, now=now)
    assert result["close"] == [120]
    assert result["as_of"] == "2026-10-19"


@pytest.mark.parametrize("bad", [float("nan"),float("inf"),0,-10])
def test_invalid_prices_are_rejected_instead_of_inventing_indicators(bad):
    payload = candles()
    payload["close"][-1] = bad
    with pytest.raises(ValueError, match="invalid price"):
        market.validate_history(payload)


def test_duplicate_or_misaligned_history_is_rejected():
    payload = candles()
    payload["timestamp"][-1] = payload["timestamp"][-2]
    with pytest.raises(ValueError, match="Duplicate"):
        market.validate_history(payload)
    payload["timestamp"].pop()
    with pytest.raises(ValueError, match="misaligned"):
        market.validate_history(payload)


def test_shared_history_cache_reuses_one_request_and_contains_no_authentication(tmp_path, monkeypatch):
    monkeypatch.setattr(market.settings, "ROOT", tmp_path)
    class Client:
        count = 0
        def post(self, *args, **kwargs):
            self.count += 1
            class Response:
                status_code = 200
                def json(self): return candles()
            return Response()
    client = Client()
    first = market.fetch_history(client, "NSE_EQ", "1333")
    second = market.fetch_history(client, "NSE_EQ", "1333")
    assert first == second
    assert client.count == 1
    cached = market._cache_path("NSE_EQ", "1333").read_text()
    assert "access_token" not in cached and "client_id" not in cached
    payload = json.loads(cached)
    payload["saved_at"] -= market.CACHE_TTL + 1
    market._cache_path("NSE_EQ", "1333").write_text(json.dumps(payload))
    assert market.cached_history("NSE_EQ", "1333") is None


def test_wilder_rsi_handles_flat_and_one_directional_prices():
    assert _rsi([100.0]*70) == 50
    assert _rsi([float(i) for i in range(1,71)]) == 100
    assert _rsi([float(i) for i in range(70,0,-1)]) == 0


def test_unknown_equity_is_not_silently_mapped_to_a_different_stock():
    result = market.build_holding_market_data({"portfolio":{"holdings":[{"asset_class":"equity","isin":"UNKNOWN","scheme_name":"Unverified"}]}})
    assert result["available"] is False
    assert result["holdings"] == []
    assert result["unmapped"] == ["Unverified"]


def test_dhan_history_produces_per_holding_indicators_without_broker_portfolio_calls(tmp_path, monkeypatch):
    item = {"isin":"VERIFIED", "symbol":"DEMO", "name":"Verified equity", "security_id":"1333"}
    monkeypatch.setattr(market.settings, "ROOT", tmp_path)
    monkeypatch.setattr(market, "instrument_catalogue", lambda: [item])
    monkeypatch.setattr(market, "resolve_dhan_auth", lambda **kwargs: ("fixture-client", "fixture-token"))
    paths = []
    class Client:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def post(self, url, **kwargs):
            paths.append(url)
            assert url.endswith("/charts/historical")
            class Response:
                status_code=200
                def json(self): return candles()
            return Response()
    monkeypatch.setattr(market, "_dhan_client", lambda *args: Client())
    result = market.build_holding_market_data({"portfolio":{"holdings":[{"asset_class":"equity", "isin":"VERIFIED"}]}})
    assert result["available"] is True
    row = result["holdings"][0]
    assert row["indicators"]["rsi_14"] == 100
    assert row["indicators"]["rs_20d"] == 0
    assert row["candles"] >= 55
    assert len(paths) == 2


def test_equity_payload_receives_dated_dhan_evidence(monkeypatch):
    from ai_cio.services.agents import equity_agent
    monkeypatch.setattr(equity_agent, "fetch_sector_day_changes", lambda: pytest.fail("Do not fetch a separate undated feed"))
    evidence = {"available": True, "holdings": [{"symbol":"DEMO", "as_of":"2026-10-19", "indicators":{"rsi_14": 52}}]}
    payload = equity_agent._equity_payload({"portfolio":{"holdings":[]}}, {}, evidence)
    assert payload["market_data"]["holding_indicators"] == evidence
    assert payload["market_data"]["live_prices_included"] is False
