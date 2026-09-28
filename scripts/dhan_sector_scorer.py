#!/usr/bin/env python3
"""Standalone POC: deterministic NSE sector opportunity scoring via Dhan historical API.

READ-ONLY. No LLM. No orders. Not investment advice.

Usage (from repo root):
  .\\.venv\\Scripts\\python.exe scripts\\dhan_sector_scorer.py

Credentials (required in .env - never hard-code):
  DHAN_CLIENT_ID=...
  DHAN_PIN=...
  DHAN_TOTP_SECRET=...
  # OR a pre-minted DHAN_ACCESS_TOKEN
"""

from __future__ import annotations

import math
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

# Allow `python scripts/dhan_sector_scorer.py` from repo root
_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import sector_config as cfg

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


# ---------------------------------------------------------------------------
# Credentials / token mint (PIN + TOTP)
# ---------------------------------------------------------------------------

def _env(*names: str) -> str:
    for name in names:
        value = (os.getenv(name) or "").strip()
        if value:
            return value
    return ""


def generate_totp(secret: str) -> str:
    try:
        import pyotp
    except ImportError as exc:
        raise RuntimeError(
            "pyotp is required to mint a Dhan token from DHAN_TOTP_SECRET. "
            "Install with: pip install pyotp"
        ) from exc
    return pyotp.TOTP(secret.replace(" ", "")).now()


def mint_access_token(client_id: str, pin: str, totp_code: str) -> str:
    """POST generateAccessToken - returns access token string. Never prints secrets."""
    url = cfg.DHAN_GENERATE_TOKEN_URL
    params = {
        "dhanClientId": client_id,
        "pin": pin,
        "totp": totp_code,
    }
    with httpx.Client(timeout=30.0) as client:
        response = client.post(url, params=params, headers={"Accept": "application/json"})
    if response.status_code >= 400:
        raise RuntimeError(f"Token mint HTTP {response.status_code}: {response.text[:400]}")

    # Response may be JSON or plain text depending on Dhan version
    token = ""
    content_type = (response.headers.get("content-type") or "").lower()
    if "json" in content_type:
        data = response.json()
        if isinstance(data, dict):
            if str(data.get("status", "")).lower() == "failure":
                raise RuntimeError(f"Token mint failed: {data.get('remarks') or data}")
            token = (
                data.get("accessToken")
                or data.get("access_token")
                or data.get("token")
                or ""
            )
            if not token and isinstance(data.get("data"), dict):
                nested = data["data"]
                token = nested.get("accessToken") or nested.get("access_token") or ""
        elif isinstance(data, str):
            token = data
    else:
        token = response.text.strip().strip('"')

    if not token or len(token) < 20:
        raise RuntimeError(
            f"Token mint returned no usable accessToken. Body preview: {response.text[:300]}"
        )
    return str(token).strip()


def resolve_access_token(client_id: str) -> tuple[str, str]:
    """Return (access_token, source_label). Prefers static token, else PIN+TOTP mint."""
    static = _env("DHAN_ACCESS_TOKEN", "DHANHQ_ACCESS_TOKEN", "DHAN_TOKEN")
    if static:
        return static, "DHAN_ACCESS_TOKEN"

    pin = _env("DHAN_PIN")
    secret = _env("DHAN_TOTP_SECRET", "DHAN_TOTP")
    if not pin or not secret:
        raise RuntimeError(
            "Need either DHAN_ACCESS_TOKEN, or both DHAN_PIN and DHAN_TOTP_SECRET "
            "to mint a token via https://auth.dhan.co/app/generateAccessToken"
        )

    totp_code = generate_totp(secret)
    print(f"Minting Dhan access token via TOTP for client_id={client_id}...")
    token = mint_access_token(client_id, pin, totp_code)
    print("Access token minted successfully (value not printed).")
    return token, "PIN+TOTP"


def load_dhan_client_id() -> str:
    return _env("DHAN_CLIENT_ID", "DHANHQ_CLIENT_ID", "DHAN_CLIENTID")


# ---------------------------------------------------------------------------
# Data fetch
# ---------------------------------------------------------------------------

@dataclass
class OHLCV:
    timestamps: list[int]
    open: list[float]
    high: list[float]
    low: list[float]
    close: list[float]
    volume: list[float]


def fetch_sector_data(
    client: httpx.Client,
    *,
    security_id: str,
    exchange_segment: str,
    instrument: str,
    from_date: str,
    to_date: str,
) -> OHLCV:
    """Fetch daily OHLCV from Dhan. Raises RuntimeError on API/empty failures."""
    payload = {
        "securityId": str(security_id),
        "exchangeSegment": exchange_segment,
        "instrument": instrument,
        "expiryCode": 0,
        "oi": False,
        "fromDate": from_date,
        "toDate": to_date,
    }
    response = client.post(cfg.DHAN_HISTORICAL_URL, json=payload)
    if response.status_code >= 400:
        raise RuntimeError(f"HTTP {response.status_code}: {response.text[:500]}")

    data = response.json()
    # Dhan sometimes wraps errors as JSON with status/failure
    if isinstance(data, dict) and str(data.get("status", "")).lower() == "failure":
        remarks = data.get("remarks") or data.get("message") or data
        raise RuntimeError(f"Dhan failure: {remarks}")

    if not isinstance(data, dict):
        raise RuntimeError(f"Unexpected response type: {type(data)}")

    closes = data.get("close") or data.get("Close")
    if not closes:
        raise RuntimeError("DATA UNAVAILABLE - no close series in response")

    def _as_float_list(key_opts: list[str]) -> list[float]:
        raw = None
        for key in key_opts:
            if key in data and data[key] is not None:
                raw = data[key]
                break
        if raw is None:
            return []
        out: list[float] = []
        for item in raw:
            if item is None:
                out.append(float("nan"))
            else:
                out.append(float(item))
        return out

    timestamps = [int(x) for x in (data.get("timestamp") or data.get("start_Time") or [])]
    opens = _as_float_list(["open", "Open"])
    highs = _as_float_list(["high", "High"])
    lows = _as_float_list(["low", "Low"])
    close = _as_float_list(["close", "Close"])
    volume = _as_float_list(["volume", "Volume"])

    n = len(close)
    if n == 0:
        raise RuntimeError("DATA UNAVAILABLE - empty close series")

    # Align optional series
    if len(opens) != n:
        opens = [float("nan")] * n
    if len(highs) != n:
        highs = [float("nan")] * n
    if len(lows) != n:
        lows = [float("nan")] * n
    if len(volume) != n:
        volume = [float("nan")] * n
    if len(timestamps) != n:
        timestamps = list(range(n))

    return OHLCV(
        timestamps=timestamps,
        open=opens,
        high=highs,
        low=lows,
        close=close,
        volume=volume,
    )


# ---------------------------------------------------------------------------
# Indicators
# ---------------------------------------------------------------------------

def _sma(values: list[float], window: int) -> float | None:
    if len(values) < window:
        return None
    chunk = values[-window:]
    if any(math.isnan(v) for v in chunk):
        return None
    return sum(chunk) / window


def _pct_return(values: list[float], lookback: int) -> float | None:
    if len(values) < lookback + 1:
        return None
    now = values[-1]
    past = values[-(lookback + 1)]
    if math.isnan(now) or math.isnan(past) or past == 0:
        return None
    return (now / past - 1.0) * 100.0


def _rsi(values: list[float], period: int = 14) -> float | None:
    if len(values) < period + 1:
        return None
    gains: list[float] = []
    losses: list[float] = []
    for i in range(1, len(values)):
        diff = values[i] - values[i - 1]
        if math.isnan(diff):
            return None
        gains.append(max(diff, 0.0))
        losses.append(max(-diff, 0.0))
    if len(gains) < period:
        return None
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


@dataclass
class Indicators:
    current_close: float | None = None
    dma_20: float | None = None
    dma_50: float | None = None
    return_20d: float | None = None
    return_50d: float | None = None
    rsi_14: float | None = None
    current_volume: float | None = None
    avg_volume_20: float | None = None
    volume_available: bool = False
    rs_20d: float | None = None
    rs_50d: float | None = None
    insufficient: bool = False
    reason: str = ""


def calculate_indicators(ohlcv: OHLCV, nifty_ind: Indicators | None = None) -> Indicators:
    closes = ohlcv.close
    volumes = ohlcv.volume
    out = Indicators()

    if len(closes) < cfg.MIN_CANDLES_REQUIRED:
        out.insufficient = True
        out.reason = f"insufficient candles ({len(closes)} < {cfg.MIN_CANDLES_REQUIRED})"
        return out

    out.current_close = closes[-1]
    out.dma_20 = _sma(closes, 20)
    out.dma_50 = _sma(closes, 50)
    out.return_20d = _pct_return(closes, 20)
    out.return_50d = _pct_return(closes, 50)
    out.rsi_14 = _rsi(closes, 14)

    # Volume: index series often all-zero / NaN - do not invent values
    last_vol = volumes[-1] if volumes else float("nan")
    avg_vol = _sma(volumes, 20)
    vol_ok = (
        not math.isnan(last_vol)
        and avg_vol is not None
        and not math.isnan(avg_vol)
        and avg_vol > 0
    )
    out.volume_available = vol_ok
    if vol_ok:
        out.current_volume = last_vol
        out.avg_volume_20 = avg_vol
    else:
        out.current_volume = None
        out.avg_volume_20 = None

    required = [out.current_close, out.dma_20, out.dma_50, out.return_20d, out.return_50d, out.rsi_14]
    if any(v is None or (isinstance(v, float) and math.isnan(v)) for v in required):
        out.insufficient = True
        out.reason = "one or more price indicators could not be calculated (NaN/missing)"
        return out

    if nifty_ind is not None and not nifty_ind.insufficient:
        if nifty_ind.return_20d is None or nifty_ind.return_50d is None:
            out.insufficient = True
            out.reason = "benchmark returns unavailable"
            return out
        out.rs_20d = out.return_20d - nifty_ind.return_20d
        out.rs_50d = out.return_50d - nifty_ind.return_50d
    elif nifty_ind is not None and nifty_ind.insufficient:
        out.insufficient = True
        out.reason = "benchmark data insufficient"
        return out

    return out


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

@dataclass
class TechnicalBreakdown:
    trend: int = 0
    momentum: int = 0
    relative_strength: int = 0
    volume: int = 0
    total: int = 0
    trend_label: str = "Weak"
    rs_label: str = "Neutral"


def calculate_technical_score(ind: Indicators) -> TechnicalBreakdown:
    bd = TechnicalBreakdown()
    assert ind.current_close is not None
    assert ind.dma_20 is not None and ind.dma_50 is not None
    assert ind.return_20d is not None and ind.return_50d is not None
    assert ind.rsi_14 is not None

    # Trend - 30
    if ind.current_close > ind.dma_20:
        bd.trend += 10
    if ind.current_close > ind.dma_50:
        bd.trend += 10
    if ind.dma_20 > ind.dma_50:
        bd.trend += 10
    bd.trend_label = "Strong" if bd.trend >= 20 else ("Mixed" if bd.trend >= 10 else "Weak")

    # Momentum - 25
    if ind.return_20d > 0:
        bd.momentum += 10
    if ind.return_50d > 0:
        bd.momentum += 10
    if 50 <= ind.rsi_14 <= 70:
        bd.momentum += 5

    # Relative strength - 25
    if ind.rs_20d is not None and ind.rs_20d > 0:
        bd.relative_strength += 10
    if ind.rs_50d is not None and ind.rs_50d > 0:
        bd.relative_strength += 15
    if bd.relative_strength >= 15:
        bd.rs_label = "Positive"
    elif bd.relative_strength == 0:
        bd.rs_label = "Negative/Flat"
    else:
        bd.rs_label = "Mixed"

    # Volume - 20 (0 if volume unavailable - do not invent)
    if ind.volume_available and ind.current_volume is not None and ind.avg_volume_20 is not None:
        if ind.current_volume > ind.avg_volume_20:
            bd.volume += 10
            if ind.return_20d > 0:
                bd.volume += 10

    bd.total = max(0, min(100, bd.trend + bd.momentum + bd.relative_strength + bd.volume))
    return bd


def calculate_diversification_score(exposure_pct: float | None, *, unmapped: bool) -> tuple[int, str]:
    if unmapped:
        return 50, "Unmapped"
    assert exposure_pct is not None
    x = exposure_pct
    if x <= 0:
        return 100, "Mapped"
    if x <= 5:
        return 90, "Mapped"
    if x <= 10:
        return 75, "Mapped"
    if x <= 15:
        return 50, "Mapped"
    if x <= 25:
        return 25, "Mapped"
    return 0, "Mapped"


def calculate_concentration_penalty(exposure_pct: float | None, *, unmapped: bool) -> int:
    if unmapped or exposure_pct is None:
        return 0
    x = exposure_pct
    if x > 25:
        return 30
    if x > 15:
        return 15
    if x > 10:
        return 5
    return 0


def calculate_final_score(
    technical: float,
    diversification: float,
    portfolio_fit: float,
    concentration_penalty: float,
) -> float:
    raw = (
        0.50 * technical
        + 0.30 * diversification
        + 0.20 * portfolio_fit
        - concentration_penalty
    )
    return max(0.0, min(100.0, raw))


# ---------------------------------------------------------------------------
# Rank / print
# ---------------------------------------------------------------------------

@dataclass
class SectorResult:
    name: str
    key: str
    status: str = "ok"  # ok | unavailable | insufficient | missing_id
    message: str = ""
    exposure_pct: float | None = None
    unmapped: bool = False
    portfolio_category: str | None = None
    indicators: Indicators = field(default_factory=Indicators)
    technical: TechnicalBreakdown = field(default_factory=TechnicalBreakdown)
    diversification_score: int = 0
    diversification_note: str = ""
    portfolio_fit_score: int = 0
    concentration_penalty: int = 0
    final_score: float = 0.0
    deprioritized: bool = False


def resolve_exposure(sector: dict[str, Any]) -> tuple[float | None, bool, str | None]:
    category = sector.get("portfolio_category")
    if not category:
        return None, True, None
    exposure = float(cfg.PORTFOLIO_EXPOSURE_PCT.get(category, 0.0))
    return exposure, False, category


def rank_sectors(results: list[SectorResult]) -> list[SectorResult]:
    scored = [r for r in results if r.status == "ok"]
    return sorted(scored, key=lambda r: r.final_score, reverse=True)


def _fmt_pct(v: float | None, signed: bool = True) -> str:
    if v is None:
        return "n/a"
    if signed:
        return f"{v:+.1f}%"
    return f"{v:.2f}%"


def _fmt_num(v: float | None, digits: int = 2) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "n/a"
    return f"{v:.{digits}f}"


def print_debug_block(r: SectorResult, nifty: Indicators) -> None:
    ind = r.indicators
    tech = r.technical
    print(f"\n--- Detail: {r.name} ---")
    if r.status != "ok":
        print(f"Status: {r.status.upper().replace('_', ' ')}")
        print(f"Message: {r.message}")
        return
    print(f"Sector: {r.name}")
    print(f"Current Close: {_fmt_num(ind.current_close)}")
    print(f"20 DMA: {_fmt_num(ind.dma_20)}")
    print(f"50 DMA: {_fmt_num(ind.dma_50)}")
    print(f"RSI: {_fmt_num(ind.rsi_14, 1)}")
    print(f"20D Return: {_fmt_pct(ind.return_20d)}")
    print(f"50D Return: {_fmt_pct(ind.return_50d)}")
    print(f"Nifty 20D Return: {_fmt_pct(nifty.return_20d)}")
    print(f"Nifty 50D Return: {_fmt_pct(nifty.return_50d)}")
    print(f"20D Relative Strength: {_fmt_pct(ind.rs_20d)}")
    print(f"50D Relative Strength: {_fmt_pct(ind.rs_50d)}")
    if ind.volume_available:
        print(f"Current Volume: {_fmt_num(ind.current_volume, 0)}")
        print(f"20D Avg Volume: {_fmt_num(ind.avg_volume_20, 0)}")
    else:
        print("Current Volume: UNAVAILABLE (index volume missing/zero - volume points = 0)")
        print("20D Avg Volume: UNAVAILABLE")
    print(f"Trend Score: {tech.trend}/30")
    print(f"Momentum Score: {tech.momentum}/25")
    print(f"Relative Strength Score: {tech.relative_strength}/25")
    print(f"Volume Score: {tech.volume}/20")
    print(f"Technical Score: {tech.total}/100")
    if r.unmapped:
        print("Portfolio Exposure: Unmapped (treated as no mapped exposure; divers=50)")
    else:
        print(f"Portfolio Exposure: {_fmt_pct(r.exposure_pct, signed=False)} ({r.portfolio_category})")
    print(f"Diversification Score: {r.diversification_score}/100 ({r.diversification_note})")
    print(f"Portfolio Fit Score: {r.portfolio_fit_score}/100 (= diversification for this POC)")
    print(f"Concentration Penalty: {r.concentration_penalty}")
    print(f"Final Score: {r.final_score:.1f}/100")
    if r.deprioritized:
        print("Classification: DEPRIORITIZED - HIGH EXISTING EXPOSURE")


def print_results(results: list[SectorResult], nifty: Indicators, nifty_status: str) -> None:
    print("\n" + "=" * 88)
    print("SECTOR OPPORTUNITY ANALYSIS")
    print("Deterministic rule-based POC - NOT investment advice. No LLM used.")
    print("=" * 88)

    if nifty_status != "ok":
        print(f"\nBENCHMARK ERROR: NIFTY 50 status={nifty_status}. Sector RS/ranking limited.")

    ranked = rank_sectors(results)

    header = (
        f"{'Sector':<28} {'Exposure':>9} {'20D':>8} {'50D':>8} {'RSI':>6} "
        f"{'Trend':<8} {'RS':<10} {'Tech':>5} {'Divers':>6} {'Pen':>4} {'Final':>6}"
    )
    print("\n" + header)
    print("-" * len(header))

    for r in ranked:
        exp = "Unmapped" if r.unmapped else _fmt_pct(r.exposure_pct, signed=False)
        print(
            f"{r.name:<28} {exp:>9} {_fmt_pct(r.indicators.return_20d):>8} "
            f"{_fmt_pct(r.indicators.return_50d):>8} {_fmt_num(r.indicators.rsi_14, 1):>6} "
            f"{r.technical.trend_label:<8} {r.technical.rs_label:<10} "
            f"{r.technical.total:>5} {r.diversification_score:>6} "
            f"{r.concentration_penalty:>4} {r.final_score:>6.1f}"
        )

    failed = [r for r in results if r.status != "ok"]
    if failed:
        print("\n# SKIPPED / FAILED SECTORS")
        for r in failed:
            print(f"- {r.name}: {r.status.upper()} - {r.message}")

    # Top 3 excluding deprioritized
    consider = [r for r in ranked if not r.deprioritized][:3]
    print("\n" + "=" * 88)
    print("TOP 3 SECTORS TO CONSIDER")
    print("RULE-BASED SECTORS FOR FURTHER REVIEW")
    print("These are NOT investment recommendations.")
    print("=" * 88)
    if not consider:
        print("No eligible sectors (all failed, insufficient, or deprioritized).")
    for i, r in enumerate(consider, start=1):
        exp = "Unmapped" if r.unmapped else f"{r.exposure_pct:.2f}%"
        print(f"\n{i}. {r.name} - Score: {r.final_score:.1f}")
        print(f"   Technical: {r.technical.total}")
        print(f"   Diversification: {r.diversification_score}")
        print(f"   Current exposure: {exp}")

    print("\n" + "=" * 88)
    print("SECTORS DEPRIORITIZED DUE TO EXISTING EXPOSURE")
    print("=" * 88)
    # Portfolio categories > 25%
    high_cats = [(k, v) for k, v in cfg.PORTFOLIO_EXPOSURE_PCT.items() if v > 25]
    if not high_cats:
        print("(none)")
    for name, exp in sorted(high_cats, key=lambda x: -x[1]):
        print(f"\n{name}")
        print(f"Exposure: {exp:.2f}%")
        print("Reason: Above 25% concentration threshold")

    deprior_sectors = [r for r in ranked if r.deprioritized]
    if deprior_sectors:
        print("\nLinked sector indices also excluded from Top 3:")
        for r in deprior_sectors:
            print(
                f"- {r.name}: exposure {r.exposure_pct:.2f}% "
                f"-> DEPRIORITIZED - HIGH EXISTING EXPOSURE (final={r.final_score:.1f})"
            )

    print("\n" + "=" * 88)
    print("PER-SECTOR CALCULATION DETAIL")
    print("=" * 88)
    for r in results:
        print_debug_block(r, nifty)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    client_id = load_dhan_client_id()
    if not client_id:
        print("ERROR: DHAN_CLIENT_ID not set in environment/.env")
        print()
        print("Required:")
        print("  DHAN_CLIENT_ID")
        print("  DHAN_PIN")
        print("  DHAN_TOTP_SECRET")
        print("Optional:")
        print("  DHAN_ACCESS_TOKEN  (skip mint if already have a token)")
        return 2

    try:
        access_token, token_source = resolve_access_token(client_id)
    except Exception as exc:
        print(f"ERROR: could not obtain Dhan access token: {exc}")
        return 2

    today = date.today()
    # toDate is non-inclusive per Dhan docs - use tomorrow
    from_date = (today - timedelta(days=cfg.HISTORY_CALENDAR_DAYS)).isoformat()
    to_date = (today + timedelta(days=1)).isoformat()

    headers = {
        "access-token": access_token,
        "client-id": client_id,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    print("Dhan Sector Opportunity Scorer (POC)")
    print(f"Auth: client_id={client_id} | token_source={token_source}")
    print(f"History window: {from_date} -> {to_date} (daily candles)")
    print(f"Sectors configured: {len(cfg.SECTORS)}")
    print("Mode: READ-ONLY historical data + deterministic scoring (no LLM, no orders)")

    nifty_ind = Indicators(insufficient=True, reason="not fetched")
    nifty_status = "unavailable"

    with httpx.Client(headers=headers, timeout=60.0) as client:
        # Benchmark
        print("\nFetching benchmark NIFTY 50...")
        try:
            if not cfg.BENCHMARK.get("security_id"):
                raise RuntimeError("missing security_id for NIFTY 50 in sector_config.BENCHMARK")
            nifty_ohlcv = fetch_sector_data(
                client,
                security_id=str(cfg.BENCHMARK["security_id"]),
                exchange_segment=str(cfg.BENCHMARK["exchange_segment"]),
                instrument=str(cfg.BENCHMARK["instrument"]),
                from_date=from_date,
                to_date=to_date,
            )
            nifty_ind = calculate_indicators(nifty_ohlcv, nifty_ind=None)
            if nifty_ind.insufficient:
                nifty_status = "insufficient"
                print(f"NIFTY 50: INSUFFICIENT DATA - {nifty_ind.reason}")
            else:
                nifty_status = "ok"
                print(
                    f"NIFTY 50: OK | close={_fmt_num(nifty_ind.current_close)} "
                    f"| 20D={_fmt_pct(nifty_ind.return_20d)} | 50D={_fmt_pct(nifty_ind.return_50d)} "
                    f"| RSI={_fmt_num(nifty_ind.rsi_14, 1)}"
                )
        except Exception as exc:
            nifty_status = "unavailable"
            print(f"NIFTY 50: DATA UNAVAILABLE - {exc}")

        results: list[SectorResult] = []
        for sector in cfg.SECTORS:
            name = sector["name"]
            sid = (sector.get("security_id") or "").strip()
            print(f"\nFetching {name} (security_id={sid or 'MISSING'})...")

            if not sid:
                results.append(
                    SectorResult(
                        name=name,
                        key=sector["key"],
                        status="missing_id",
                        message="security_id not set in scripts/sector_config.py",
                    )
                )
                print(f"Sector: {name}\nStatus: MISSING SECURITY ID")
                continue

            exposure, unmapped, category = resolve_exposure(sector)
            try:
                ohlcv = fetch_sector_data(
                    client,
                    security_id=sid,
                    exchange_segment=str(sector["exchange_segment"]),
                    instrument=str(sector["instrument"]),
                    from_date=from_date,
                    to_date=to_date,
                )
            except Exception as exc:
                results.append(
                    SectorResult(
                        name=name,
                        key=sector["key"],
                        status="unavailable",
                        message=str(exc),
                        exposure_pct=exposure,
                        unmapped=unmapped,
                        portfolio_category=category,
                    )
                )
                print(f"Sector: {name}\nStatus: DATA UNAVAILABLE\nError: {exc}")
                time.sleep(0.25)
                continue

            ind = calculate_indicators(ohlcv, nifty_ind=nifty_ind if nifty_status == "ok" else Indicators(insufficient=True, reason="benchmark failed"))
            if ind.insufficient or nifty_status != "ok":
                reason = ind.reason if ind.insufficient else "benchmark unavailable - cannot compute RS"
                results.append(
                    SectorResult(
                        name=name,
                        key=sector["key"],
                        status="insufficient",
                        message=reason,
                        exposure_pct=exposure,
                        unmapped=unmapped,
                        portfolio_category=category,
                        indicators=ind,
                    )
                )
                print(f"Sector: {name}\nStatus: INSUFFICIENT DATA - {reason}")
                time.sleep(0.25)
                continue

            tech = calculate_technical_score(ind)
            divers, divers_note = calculate_diversification_score(exposure, unmapped=unmapped)
            penalty = calculate_concentration_penalty(exposure, unmapped=unmapped)
            portfolio_fit = divers  # POC: fit == diversification
            final = calculate_final_score(tech.total, divers, portfolio_fit, penalty)
            deprior = (not unmapped) and exposure is not None and exposure > 25

            result = SectorResult(
                name=name,
                key=sector["key"],
                status="ok",
                exposure_pct=0.0 if unmapped else exposure,
                unmapped=unmapped,
                portfolio_category=category,
                indicators=ind,
                technical=tech,
                diversification_score=divers,
                diversification_note=divers_note,
                portfolio_fit_score=portfolio_fit,
                concentration_penalty=penalty,
                final_score=final,
                deprioritized=deprior,
            )
            results.append(result)
            print(
                f"Sector: {name} | Tech={tech.total} Divers={divers} "
                f"Penalty={penalty} Final={final:.1f}"
                + (" | DEPRIORITIZED" if deprior else "")
            )
            time.sleep(0.25)

    print_results(results, nifty_ind, nifty_status)
    return 0 if nifty_status == "ok" and any(r.status == "ok" for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
