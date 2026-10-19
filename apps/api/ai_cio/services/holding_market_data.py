"""Read-only Dhan daily candles, bounded shared caching and deterministic indicators.

Never reads broker positions, account balances, orders or private trade history.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import threading
import time
from typing import Any
from zoneinfo import ZoneInfo
from uuid import uuid4

from ai_cio import settings
from ai_cio.services.sector_opportunity import (
    DHAN_HISTORICAL_URL, _dhan_client, _indicators, _is_invalid_token_error, resolve_dhan_auth,
)

IST = ZoneInfo("Asia/Kolkata")
CACHE_TTL = 300
_lock = threading.Lock()
_last_request = 0.0


def instrument_catalogue() -> list[dict[str, str]]:
    path = Path(settings.ROOT) / "knowledge" / "dhan_instruments.json"
    return json.loads(path.read_text(encoding="utf-8"))["instruments"]


def _cache_path(segment: str, security_id: str) -> Path:
    key = hashlib.sha256(f"{segment}:{security_id}".encode()).hexdigest()
    folder = "market-cache-test" if os.getenv("AICIO_TESTING") == "1" else "market-cache"
    return Path(settings.ROOT) / ".dev" / folder / f"{key}.json"


def cached_history(segment: str, security_id: str) -> dict | None:
    try:
        data = json.loads(_cache_path(segment, security_id).read_text(encoding="utf-8"))
        age = time.time() - float(data["saved_at"])
        if not 0 <= age < CACHE_TTL or data.get("trading_date") != datetime.now(IST).date().isoformat():
            return None
        history = data["history"]
        validated = validate_history(history)
        validated["fetched_at"] = history["fetched_at"]
        return validated
    except (OSError, ValueError, KeyError, TypeError):
        return None


def validate_history(data: dict, *, now: datetime | None = None) -> dict:
    """Use finite, unique, ordered, completed daily candles only."""
    now = now or datetime.now(IST)
    now = now.astimezone(IST)
    closes, stamps, volumes = data.get("close", []), data.get("timestamp", []), data.get("volume", [])
    if not closes or len(closes) != len(stamps):
        raise ValueError("Daily candle prices and timestamps are missing or misaligned")
    rows = {}
    for index, (price, stamp) in enumerate(zip(closes, stamps)):
        price, stamp = float(price), float(stamp)
        if not math.isfinite(price) or price <= 0 or not math.isfinite(stamp):
            raise ValueError("Daily candle contains an invalid price or timestamp")
        day = datetime.fromtimestamp(stamp, IST).date()
        # Dhan may include an unfinished current-session candle. Do not use it.
        if day > now.date() or (day == now.date() and (now.hour, now.minute) < (15, 30)):
            continue
        if stamp in rows:
            raise ValueError("Duplicate daily candle timestamp")
        volume = volumes[index] if index < len(volumes) else None
        volume = float(volume) if volume is not None else None
        volume = volume if volume is not None and math.isfinite(volume) and volume >= 0 else None
        rows[stamp] = (price, volume)
    ordered = sorted(rows)
    if not ordered:
        raise ValueError("No completed daily candles")
    as_of = datetime.fromtimestamp(ordered[-1], IST).date()
    if (now.date() - as_of).days > 7:
        raise ValueError("Latest daily candle is older than seven calendar days")
    return {
        "close": [rows[t][0] for t in ordered],
        "volume": [rows[t][1] for t in ordered],
        "timestamp": ordered,
        "as_of": as_of.isoformat(),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source": "Dhan daily historical candles",
        "timeframe": "completed daily candles; not streaming quotes",
    }


def fetch_history(client, segment: str, security_id: str) -> dict:
    global _last_request
    with _lock:
        cached = cached_history(segment, security_id)
        if cached:
            return deepcopy(cached)
        # Data API limit is five requests/second. Serialize cache misses.
        time.sleep(max(0, 0.25 - (time.monotonic() - _last_request)))
        today = datetime.now(IST).date()
        try:
            response = client.post(DHAN_HISTORICAL_URL, json={
                "securityId": str(security_id), "exchangeSegment": segment,
                "instrument": "INDEX" if segment == "IDX_I" else "EQUITY",
                "expiryCode": 0, "oi": False,
                "fromDate": (today - timedelta(days=220)).isoformat(),
                "toDate": (today + timedelta(days=1)).isoformat(),
            })
        finally:
            _last_request = time.monotonic()
        if response.status_code != 200:
            code = response.status_code
            raise RuntimeError("Dhan token expired or unauthorized" if code in (401, 403) else f"Dhan historical data unavailable (HTTP {code})")
        body = response.json()
        if body.get("errorCode") or body.get("errorType") or body.get("status") == "failure":
            code = str(body.get("errorCode") or "provider_error")
            raise RuntimeError(f"Dhan historical data unavailable ({code})")
        history = validate_history(body)
        path = _cache_path(segment, security_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"saved_at": time.time(), "trading_date": today.isoformat(), "history": history}
        temporary = path.with_suffix(f".{uuid4().hex}.tmp")
        try:
            temporary.write_text(json.dumps(payload, allow_nan=False), encoding="utf-8")
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
        return history


def build_holding_market_data(twin: dict[str, Any]) -> dict:
    holdings = (twin.get("portfolio") or {}).get("holdings") or []
    mapping = {item["isin"]: item for item in instrument_catalogue()}
    mapped, unmapped = [], []
    for holding in holdings:
        if holding.get("asset_class") != "equity" and holding.get("amc") != "EQUITY":
            continue
        item = mapping.get(holding.get("isin"))
        if item:
            mapped.append((holding, item))
        else:
            unmapped.append(holding.get("scheme_name") or "Unmapped equity")
    base = {"available": False, "source": "Dhan", "holdings": [], "unmapped": unmapped,
            "failed": [], "methodology": "SMA20/50, Wilder RSI14, 20/50-session price returns and excess returns versus NIFTY 50. Price returns exclude dividends. Signals are review context, not forecasts or suitability scores.",
            "price_basis": "Latest completed daily candle; not a live streaming quote."}
    if not mapped:
        return {**base, "reason": "No directly held equities with a verified Dhan security mapping"}
    try:
        client_id, token = resolve_dhan_auth()
    except Exception:
        return {**base, "reason": "Dhan market credentials are unavailable; no market indicators were invented."}
    for attempt in range(2):
        try:
            with _dhan_client(client_id, token) as client:
                benchmark = fetch_history(client, "IDX_I", "13")
                bench = _indicators(benchmark["close"], [v if v is not None else float("nan") for v in benchmark["volume"]], None)
                if bench.get("insufficient"):
                    return {**base, "reason": "Insufficient NIFTY 50 benchmark history"}
                rows, failed = [], []
                for holding, item in mapped:
                    try:
                        history = fetch_history(client, "NSE_EQ", item["security_id"])
                        stock_days = [datetime.fromtimestamp(t, IST).date() for t in history["timestamp"][-51:]]
                        benchmark_days = [datetime.fromtimestamp(t, IST).date() for t in benchmark["timestamp"][-51:]]
                        if stock_days != benchmark_days:
                            raise ValueError("Stock and benchmark sessions do not align")
                        indicators = _indicators(history["close"], [v if v is not None else float("nan") for v in history["volume"]], bench)
                        if indicators.get("insufficient"):
                            raise ValueError("Insufficient history for indicators")
                        rows.append({**item, "as_of": history["as_of"], "fetched_at": history["fetched_at"],
                                     "candles": len(history["close"]), "indicators": indicators})
                    except Exception as exc:
                        if _is_invalid_token_error(exc):
                            raise
                        failed.append({"name": item["name"], "reason": str(exc) if isinstance(exc, ValueError) else "Dhan history unavailable"})
                return {**base, "available": bool(rows), "holdings": rows, "failed": failed,
                        "reason": None if rows else "No usable holding histories were returned", "benchmark": {"name": "NIFTY 50", "as_of": benchmark["as_of"]}}
        except Exception as exc:
            if attempt == 0 and _is_invalid_token_error(exc):
                try:
                    client_id, token = resolve_dhan_auth(force_refresh=True)
                    continue
                except Exception:
                    pass
            return {**base, "reason": "Dhan market data is unavailable. Check token validity and data permissions; no indicators were invented."}
    return base
