"""Deterministic NSE sector opportunity scoring (Dhan historical data).

No LLM. READ-ONLY market data. Educational review aid — not buy/sell advice.
"""
from __future__ import annotations

import json
import logging
import math
import os
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import httpx

from ai_cio import settings

logger = logging.getLogger(__name__)

DHAN_HISTORICAL_URL = "https://api.dhan.co/v2/charts/historical"
DHAN_GENERATE_TOKEN_URL = "https://auth.dhan.co/app/generateAccessToken"

BENCHMARK = {
    "key": "NIFTY_50",
    "name": "NIFTY 50",
    "security_id": "13",
    "exchange_segment": "IDX_I",
    "instrument": "INDEX",
}

SECTOR_UNIVERSE: list[dict[str, Any]] = [
    {"key": "NIFTY_IT", "name": "NIFTY IT", "security_id": "29", "portfolio_categories": []},
    {"key": "NIFTY_PHARMA", "name": "NIFTY PHARMA", "security_id": "32", "portfolio_categories": ["Healthcare / Pharma"]},
    {"key": "NIFTY_AUTO", "name": "NIFTY AUTO", "security_id": "14", "portfolio_categories": []},
    {"key": "NIFTY_FMCG", "name": "NIFTY FMCG", "security_id": "28", "portfolio_categories": ["FMCG / Consumer"]},
    {"key": "NIFTY_METAL", "name": "NIFTY METAL", "security_id": "31", "portfolio_categories": ["Metals / Resources"]},
    {"key": "NIFTY_REALTY", "name": "NIFTY REALTY", "security_id": "34", "portfolio_categories": []},
    {"key": "NIFTY_ENERGY", "name": "NIFTY ENERGY", "security_id": "42", "portfolio_categories": []},
    {
        "key": "NIFTY_INFRASTRUCTURE",
        "name": "NIFTY INFRASTRUCTURE",
        "security_id": "43",
        "portfolio_categories": ["Industrials / Capital Goods"],
    },
    {
        "key": "NIFTY_CONSUMER_DURABLES",
        "name": "NIFTY CONSUMER DURABLES",
        "security_id": "466",
        "portfolio_categories": ["FMCG / Consumer"],
    },
    {
        "key": "NIFTY_HEALTHCARE",
        "name": "NIFTY HEALTHCARE",
        "security_id": "447",
        "portfolio_categories": ["Healthcare / Pharma"],
    },
    {"key": "NIFTY_MEDIA", "name": "NIFTY MEDIA", "security_id": "30", "portfolio_categories": []},
    {
        "key": "NIFTY_PSU_BANK",
        "name": "NIFTY PSU BANK",
        "security_id": "33",
        "portfolio_categories": ["Financials / Banks"],
    },
    {
        "key": "NIFTY_FINANCIAL_SERVICES",
        "name": "NIFTY FINANCIAL SERVICES",
        "security_id": "27",
        "portfolio_categories": ["Financials / Banks"],
    },
    {
        "key": "NIFTY_BANK",
        "name": "NIFTY BANK",
        "security_id": "25",
        "portfolio_categories": ["Financials / Banks"],
    },
]

HISTORY_CALENDAR_DAYS = 220
MIN_CANDLES = 55


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
    now, past = values[-1], values[-(lookback + 1)]
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


def _mint_token(client_id: str, pin: str, totp_secret: str) -> str:
    import pyotp

    secret = totp_secret.replace(" ", "").upper()
    totp_gen = pyotp.TOTP(secret)
    # Try current / previous / next 30s window (handles mild clock skew).
    codes: list[str] = []
    for offset in (0, -1, 1):
        code = totp_gen.at(int(time.time()) + offset * 30)
        if code not in codes:
            codes.append(code)

    last_error = "unknown"
    with httpx.Client(timeout=30.0) as client:
        for totp in codes:
            resp = client.post(
                DHAN_GENERATE_TOKEN_URL,
                params={"dhanClientId": client_id, "pin": pin, "totp": totp},
                headers={"Accept": "application/json"},
            )
            if resp.status_code >= 400:
                last_error = f"HTTP {resp.status_code}: {resp.text[:300]}"
                continue

            content_type = (resp.headers.get("content-type") or "").lower()
            data: Any
            if "json" in content_type:
                data = resp.json()
            else:
                text = (resp.text or "").strip()
                try:
                    data = json.loads(text) if text.startswith("{") else text
                except json.JSONDecodeError:
                    data = text

            if isinstance(data, dict):
                status = str(data.get("status") or "").lower()
                if status in {"error", "failure", "failed"}:
                    last_error = str(data.get("message") or data.get("remarks") or data)
                    # Rate limit: don't burn more TOTP attempts.
                    if "2 minutes" in last_error.lower() or "once every" in last_error.lower():
                        raise RuntimeError(last_error)
                    continue
                token = (
                    data.get("accessToken")
                    or data.get("access_token")
                    or data.get("token")
                    or ""
                )
                if not token and isinstance(data.get("data"), dict):
                    nested = data["data"]
                    token = (
                        nested.get("accessToken")
                        or nested.get("access_token")
                        or nested.get("token")
                        or ""
                    )
            else:
                token = str(data or "").strip().strip('"')

            if token and len(str(token)) >= 20:
                return str(token).strip()
            last_error = f"no accessToken (preview: {str(data)[:180]})"

    raise RuntimeError(last_error)


def _is_mint_rate_limited(exc: BaseException | str) -> bool:
    text = str(exc).lower()
    return "2 minutes" in text or "once every" in text


def _mint_token_with_rate_limit_wait(
    client_id: str, pin: str, totp_secret: str, *, wait_seconds: float = 125.0
) -> str:
    """Mint, and if Dhan rate-limits (once / 2 min), wait once then retry."""
    try:
        return _mint_token(client_id, pin, totp_secret)
    except Exception as exc:
        if not _is_mint_rate_limited(exc):
            raise
        logger.warning(
            "dhan_token_mint_rate_limited waiting_s=%.0f err=%s", wait_seconds, exc
        )
        time.sleep(wait_seconds)
        return _mint_token(client_id, pin, totp_secret)


def _token_cache_path() -> Path:
    return Path(settings.ROOT) / "data" / "dhan" / "token.json"


def _load_cached_token(client_id: str, *, allow_stale: bool = False) -> str | None:
    path = _token_cache_path()
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if str(payload.get("client_id") or "") != str(client_id):
        return None
    token = str(payload.get("access_token") or "").strip()
    if len(token) < 20:
        return None
    expires_at = payload.get("expires_at")
    if expires_at is not None and not allow_stale:
        try:
            if float(expires_at) <= time.time() + 60:
                return None
        except (TypeError, ValueError):
            pass
    return token


def _save_cached_token(client_id: str, token: str, *, ttl_hours: float = 20.0) -> None:
    path = _token_cache_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "client_id": client_id,
                    "access_token": token,
                    "expires_at": time.time() + ttl_hours * 3600,
                    "saved_at": time.time(),
                }
            ),
            encoding="utf-8",
        )
    except Exception as exc:
        logger.warning("dhan_token_cache_write_failed err=%s", exc)


def _clear_cached_token(client_id: str | None = None) -> None:
    path = _token_cache_path()
    if not path.exists():
        return
    try:
        if client_id:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if str(payload.get("client_id") or "") not in {"", str(client_id)}:
                return
        path.unlink(missing_ok=True)
    except Exception as exc:
        logger.warning("dhan_token_cache_clear_failed err=%s", exc)


def _is_invalid_token_error(exc: BaseException | str) -> bool:
    text = str(exc).lower()
    return any(
        marker in text
        for marker in (
            "invalid token",
            "dh-906",
            "dh-901",
            "token expired",
            "token is expired",
            "unauthorized",
        )
    )


def _live_dhan_env() -> dict[str, str]:
    """Re-read .env on each call so API restarts are not required after adding keys."""
    from dotenv import load_dotenv

    if os.getenv("AICIO_TESTING") != "1":
        load_dotenv(Path(os.getenv("AICIO_ENV_FILE", str(Path(settings.ROOT) / ".env"))), override=False)
    return {
        "client_id": (os.getenv("DHAN_CLIENT_ID") or settings.DHAN_CLIENT_ID or "").strip(),
        "access_token": (os.getenv("DHAN_ACCESS_TOKEN") or settings.DHAN_ACCESS_TOKEN or "").strip(),
        "pin": (os.getenv("DHAN_PIN") or settings.DHAN_PIN or "").strip(),
        "totp_secret": (os.getenv("DHAN_TOTP_SECRET") or settings.DHAN_TOTP_SECRET or "").strip(),
    }


def resolve_dhan_auth(*, force_refresh: bool = False) -> tuple[str, str]:
    """Return (client_id, access_token) or raise RuntimeError with a clear reason."""
    creds = _live_dhan_env()
    client_id = creds["client_id"]
    if not client_id:
        raise RuntimeError(
            "DHAN_CLIENT_ID is missing. Add it to the project .env and retry "
            "(or restart the API if it was started before the keys were added)."
        )

    # Static env token wins unless caller forces a PIN+TOTP remint.
    if creds["access_token"] and not force_refresh:
        return client_id, creds["access_token"]

    if force_refresh:
        _clear_cached_token(client_id)
    else:
        cached = _load_cached_token(client_id)
        if cached:
            return client_id, cached

    pin, secret = creds["pin"], creds["totp_secret"]
    if not pin or not secret:
        if force_refresh and creds["access_token"]:
            # Can't remint; surface that the static token is bad.
            raise RuntimeError(
                "Dhan access token is invalid/expired. Update DHAN_ACCESS_TOKEN, "
                "or set DHAN_PIN + DHAN_TOTP_SECRET so the API can remint."
            )
        raise RuntimeError(
            "Dhan auth incomplete: set DHAN_ACCESS_TOKEN, or both DHAN_PIN and "
            "DHAN_TOTP_SECRET in .env (API process must see these values)."
        )

    try:
        # On forced refresh (invalid token), wait out Dhan's 2-minute mint cooldown.
        if force_refresh:
            token = _mint_token_with_rate_limit_wait(client_id, pin, secret)
        else:
            token = _mint_token(client_id, pin, secret)
    except Exception as exc:
        # Rate-limit / transient mint errors: reuse last token if we have one
        # (unless force_refresh, where the cache was already rejected as invalid).
        if not force_refresh:
            stale = _load_cached_token(client_id, allow_stale=True)
            if stale:
                logger.warning("dhan_token_mint_failed_using_cache err=%s", exc)
                return client_id, stale
        raise RuntimeError(f"Dhan token mint failed: {exc}") from exc
    _save_cached_token(client_id, token)
    return client_id, token


def _fetch_ohlcv(client: httpx.Client, security_id: str, from_date: str, to_date: str) -> tuple[list[float], list[float]]:
    from ai_cio.services.holding_market_data import fetch_history

    history = fetch_history(client, "IDX_I", security_id)
    return history["close"], [v if v is not None else float("nan") for v in history["volume"]]


def _dhan_client(client_id: str, token: str) -> httpx.Client:
    return httpx.Client(
        headers={
            "access-token": token,
            "client-id": client_id,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        timeout=45.0,
    )


def _indicators(closes: list[float], volumes: list[float], bench: dict[str, float | None] | None) -> dict[str, Any]:
    if len(closes) < MIN_CANDLES:
        return {"insufficient": True, "reason": f"need {MIN_CANDLES} candles, got {len(closes)}"}
    current = closes[-1]
    dma20 = _sma(closes, 20)
    dma50 = _sma(closes, 50)
    r20 = _pct_return(closes, 20)
    r50 = _pct_return(closes, 50)
    rsi = _rsi(closes, 14)
    if None in (dma20, dma50, r20, r50, rsi) or any(
        isinstance(v, float) and math.isnan(v) for v in (current, dma20, dma50, r20, r50, rsi)  # type: ignore[arg-type]
    ):
        return {"insufficient": True, "reason": "indicator NaN/missing"}

    avg_vol = _sma(volumes, 20)
    last_vol = volumes[-1]
    vol_ok = avg_vol is not None and not math.isnan(avg_vol) and avg_vol > 0 and not math.isnan(last_vol)

    out: dict[str, Any] = {
        "insufficient": False,
        "current_close": current,
        "dma_20": dma20,
        "dma_50": dma50,
        "return_20d": r20,
        "return_50d": r50,
        "rsi_14": rsi,
        "volume_available": vol_ok,
        "current_volume": last_vol if vol_ok else None,
        "avg_volume_20": avg_vol if vol_ok else None,
        "rs_20d": None,
        "rs_50d": None,
    }
    if bench and bench.get("return_20d") is not None and bench.get("return_50d") is not None:
        out["rs_20d"] = float(r20) - float(bench["return_20d"])  # type: ignore[arg-type]
        out["rs_50d"] = float(r50) - float(bench["return_50d"])  # type: ignore[arg-type]
    return out


def _technical_score(ind: dict[str, Any]) -> dict[str, Any]:
    trend = 0
    if ind["current_close"] > ind["dma_20"]:
        trend += 10
    if ind["current_close"] > ind["dma_50"]:
        trend += 10
    if ind["dma_20"] > ind["dma_50"]:
        trend += 10

    momentum = 0
    if ind["return_20d"] > 0:
        momentum += 10
    if ind["return_50d"] > 0:
        momentum += 10
    if 50 <= ind["rsi_14"] <= 70:
        momentum += 5

    rs = 0
    if ind.get("rs_20d") is not None and ind["rs_20d"] > 0:
        rs += 10
    if ind.get("rs_50d") is not None and ind["rs_50d"] > 0:
        rs += 15

    volume = 0
    if ind.get("volume_available") and ind.get("current_volume") is not None and ind.get("avg_volume_20"):
        if ind["current_volume"] > ind["avg_volume_20"]:
            volume += 10
            if ind["return_20d"] > 0:
                volume += 10

    total = max(0, min(100, trend + momentum + rs + volume))
    trend_label = "Strong" if trend >= 20 else ("Mixed" if trend >= 10 else "Weak")
    rs_label = "Positive" if rs >= 15 else ("Mixed" if rs > 0 else "Negative/Flat")
    return {
        "trend": trend,
        "momentum": momentum,
        "relative_strength": rs,
        "volume": volume,
        "total": total,
        "trend_label": trend_label,
        "rs_label": rs_label,
    }


def _diversification(exposure: float | None, unmapped: bool) -> tuple[int, str]:
    if unmapped:
        return 50, "Unmapped"
    assert exposure is not None
    if exposure <= 0:
        return 100, "Mapped"
    if exposure <= 5:
        return 90, "Mapped"
    if exposure <= 10:
        return 75, "Mapped"
    if exposure <= 15:
        return 50, "Mapped"
    if exposure <= 25:
        return 25, "Mapped"
    return 0, "Mapped"


def _penalty(exposure: float | None, unmapped: bool) -> int:
    if unmapped or exposure is None:
        return 0
    if exposure > 25:
        return 30
    if exposure > 15:
        return 15
    if exposure > 10:
        return 5
    return 0


def _logic_blurb(row: dict[str, Any]) -> str:
    """Plain-language logic (not formula dump)."""
    parts: list[str] = []
    tech = row["technical"]
    parts.append(
        f"Technical posture looks {tech['trend_label'].lower()} vs its own averages, "
        f"with relative strength vs Nifty 50 marked {tech['rs_label'].lower()}."
    )
    if row["unmapped"]:
        parts.append(
            "This index is not mapped to a Twin sector label, so diversification is scored neutrally "
            "(neither rewarded nor treated as already owned)."
        )
    else:
        exp = row["exposure_pct"]
        if exp > 25:
            parts.append(
                f"Your Twin already shows ~{exp:.1f}% in {row['portfolio_category']} — "
                "above the 25% concentration gate, so this is deprioritized for new money."
            )
        elif exp <= 5:
            parts.append(
                f"Your Twin only has ~{exp:.1f}% in {row['portfolio_category']}, "
                "so diversification benefit is high if you review this theme for new equity."
            )
        else:
            parts.append(
                f"Existing exposure in {row['portfolio_category']} is ~{exp:.1f}% — "
                "moderate diversification benefit, not a blank slate."
            )
    parts.append(
        "Final rank blends market structure (half) with diversification benefit (half), "
        "then subtracts a concentration penalty when you already own a lot of the theme."
    )
    return " ".join(parts)


def exposure_map_from_twin(
    twin: dict[str, Any] | None,
    sector_allocation: list[dict[str, Any]] | None = None,
    true_exposure: dict[str, Any] | None = None,
) -> dict[str, float]:
    """Build portfolio category % from decision true_exposure / sector_allocation."""
    out: dict[str, float] = {}
    rows: list[dict[str, Any]] = []
    if true_exposure and isinstance(true_exposure.get("sector_exposure"), list):
        rows = list(true_exposure["sector_exposure"])
    elif sector_allocation:
        rows = list(sector_allocation)
    else:
        pre = (twin or {}).get("preanalysis") or {}
        rows = list(pre.get("sector_allocation") or [])

    for row in rows:
        name = str(row.get("sector") or "").strip()
        if not name or name in {"Unknown", "Unclassified"}:
            continue
        raw = row.get("percent") or row.get("weight_percent")
        try:
            pct = float(raw)
        except (TypeError, ValueError):
            continue
        out[name] = out.get(name, 0.0) + pct
    return out


def build_sector_opportunity(
    twin: dict[str, Any] | None = None,
    *,
    sector_allocation: list[dict[str, Any]] | None = None,
    true_exposure: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run Dhan fetch + deterministic scoring. Never raises to caller — returns status."""
    try:
        client_id, token = resolve_dhan_auth()
    except Exception as exc:
        logger.warning("dhan_auth_unavailable err=%s", exc)
        return {
            "available": False,
            "reason": str(exc),
            "sectors": [],
            "recommendations": [],
            "deprioritized": [],
            "methodology": _methodology(),
        }

    exposure_by_cat = exposure_map_from_twin(twin, sector_allocation, true_exposure)
    today = date.today()
    from_date = (today - timedelta(days=HISTORY_CALENDAR_DAYS)).isoformat()
    to_date = (today + timedelta(days=1)).isoformat()

    sectors_out: list[dict[str, Any]] = []
    failed: list[dict[str, str]] = []
    bench_returns: dict[str, float | None] = {}

    try:
        # Retry once after remint when Dhan rejects a cached/static token (DH-906).
        for attempt in range(2):
            try:
                with _dhan_client(client_id, token) as client:
                    b_closes, b_vols = _fetch_ohlcv(
                        client, BENCHMARK["security_id"], from_date, to_date
                    )
                    bench_ind = _indicators(b_closes, b_vols, None)
                    if bench_ind.get("insufficient"):
                        return {
                            "available": False,
                            "reason": f"NIFTY 50 benchmark insufficient: {bench_ind.get('reason')}",
                            "sectors": [],
                            "recommendations": [],
                            "deprioritized": [],
                            "methodology": _methodology(),
                        }
                    bench_returns = {
                        "return_20d": bench_ind["return_20d"],
                        "return_50d": bench_ind["return_50d"],
                    }

                    for sector in SECTOR_UNIVERSE:
                        time.sleep(0.15)
                        cats = list(sector.get("portfolio_categories") or [])
                        if cats:
                            exposure = sum(exposure_by_cat.get(c, 0.0) for c in cats)
                            # Prefer primary category label
                            category = cats[0]
                            # If Banks categories - use max of mapped for display when Financials/Banks present
                            if "Financials / Banks" in cats:
                                exposure = exposure_by_cat.get("Financials / Banks", exposure)
                                category = "Financials / Banks"
                            unmapped = False
                        else:
                            exposure = None
                            category = None
                            unmapped = True

                        try:
                            closes, volumes = _fetch_ohlcv(
                                client, sector["security_id"], from_date, to_date
                            )
                            ind = _indicators(closes, volumes, bench_returns)
                            if ind.get("insufficient"):
                                failed.append(
                                    {"name": sector["name"], "reason": str(ind.get("reason"))}
                                )
                                continue
                            tech = _technical_score(ind)
                            divers, divers_note = _diversification(exposure, unmapped)
                            penalty = _penalty(exposure, unmapped)
                            final = max(
                                0.0,
                                min(
                                    100.0,
                                    0.50 * tech["total"] + 0.50 * divers - penalty,
                                ),
                            )
                            deprior = (not unmapped) and exposure is not None and exposure > 25
                            row = {
                                "key": sector["key"],
                                "name": sector["name"],
                                "exposure_pct": 0.0 if unmapped else float(exposure or 0.0),
                                "unmapped": unmapped,
                                "portfolio_category": category,
                                "return_20d": round(ind["return_20d"], 2),
                                "return_50d": round(ind["return_50d"], 2),
                                "rsi_14": round(ind["rsi_14"], 1),
                                "dma_20": round(ind["dma_20"], 2),
                                "dma_50": round(ind["dma_50"], 2),
                                "current_close": round(ind["current_close"], 2),
                                "rs_20d": round(ind["rs_20d"], 2)
                                if ind.get("rs_20d") is not None
                                else None,
                                "rs_50d": round(ind["rs_50d"], 2)
                                if ind.get("rs_50d") is not None
                                else None,
                                "technical": tech,
                                "diversification_score": divers,
                                "diversification_note": divers_note,
                                "concentration_penalty": penalty,
                                "final_score": round(final, 1),
                                "deprioritized": deprior,
                                "classification": (
                                    "DEPRIORITIZED — HIGH EXISTING EXPOSURE"
                                    if deprior
                                    else "ELIGIBLE"
                                ),
                            }
                            row["logic"] = _logic_blurb(row)
                            sectors_out.append(row)
                        except Exception as exc:
                            if _is_invalid_token_error(exc):
                                raise
                            failed.append({"name": sector["name"], "reason": str(exc)})
                            logger.info(
                                "sector_fetch_failed name=%s err=%s", sector["name"], exc
                            )
                break
            except Exception as exc:
                if attempt == 0 and _is_invalid_token_error(exc):
                    logger.warning("dhan_token_rejected reminting err=%s", exc)
                    try:
                        client_id, token = resolve_dhan_auth(force_refresh=True)
                    except Exception as mint_exc:
                        return {
                            "available": False,
                            "reason": (
                                f"Could not fetch NIFTY 50 from Dhan: {exc}. "
                                f"Remint failed: {mint_exc}"
                            ),
                            "sectors": [],
                            "recommendations": [],
                            "deprioritized": [],
                            "methodology": _methodology(),
                        }
                    sectors_out = []
                    failed = []
                    continue
                return {
                    "available": False,
                    "reason": f"Could not fetch NIFTY 50 from Dhan: {exc}",
                    "sectors": [],
                    "recommendations": [],
                    "deprioritized": [],
                    "methodology": _methodology(),
                }
    except Exception as exc:
        return {
            "available": False,
            "reason": f"Dhan session failed: {exc}",
            "sectors": [],
            "recommendations": [],
            "deprioritized": [],
            "methodology": _methodology(),
        }

    ranked = sorted(sectors_out, key=lambda r: r["final_score"], reverse=True)
    recommendations = []
    for row in ranked:
        if row["deprioritized"]:
            continue
        recommendations.append(
            {
                "rank": len(recommendations) + 1,
                "name": row["name"],
                "final_score": row["final_score"],
                "technical_score": row["technical"]["total"],
                "diversification_score": row["diversification_score"],
                "exposure_pct": row["exposure_pct"],
                "unmapped": row["unmapped"],
                "portfolio_category": row["portfolio_category"],
                "trend_label": row["technical"]["trend_label"],
                "rs_label": row["technical"]["rs_label"],
                "logic": row["logic"],
                "label": "Rule-based sector for further review",
            }
        )
        if len(recommendations) >= 3:
            break

    deprioritized = [
        {
            "name": row["name"],
            "exposure_pct": row["exposure_pct"],
            "portfolio_category": row["portfolio_category"],
            "final_score": row["final_score"],
            "reason": "Above 25% Twin sector concentration threshold",
            "logic": row["logic"],
        }
        for row in ranked
        if row["deprioritized"]
    ]
    # Also list high Twin categories even if no index mapped cleanly
    high_cats = [
        {"name": k, "exposure_pct": v, "reason": "Above 25% concentration threshold"}
        for k, v in sorted(exposure_by_cat.items(), key=lambda x: -x[1])
        if v > 25
    ]

    return {
        "available": True,
        "benchmark": {
            "name": "NIFTY 50",
            "return_20d": round(float(bench_returns["return_20d"]), 2),  # type: ignore[arg-type]
            "return_50d": round(float(bench_returns["return_50d"]), 2),  # type: ignore[arg-type]
        },
        "sectors": ranked,
        "recommendations": recommendations,
        "deprioritized": deprioritized,
        "high_exposure_categories": high_cats,
        "failed": failed,
        "exposure_source": "twin_true_exposure" if exposure_by_cat else "empty",
        "methodology": _methodology(),
        "disclaimer": (
            "Rule-based sector opportunity scores for review only — not investment advice, "
            "not a buy/sell instruction, and not SEBI-registered advice."
        ),
    }


def _methodology() -> str:
    return (
        "Deterministic scoring from Dhan daily OHLCV: Technical Score (trend, momentum, "
        "relative strength vs Nifty 50, volume) is blended 50/50 with Diversification Score "
        "from Twin sector exposure. Sectors already >25% of equity are deprioritized. No LLM "
        "is used for ranking."
    )


def rule_based_suggestions(sector_payload: dict[str, Any], analysis_bits: dict[str, Any]) -> list[dict[str, str]]:
    """Fallback / always-on suggestions without calling an LLM."""
    out: list[dict[str, str]] = []
    for rec in (sector_payload.get("recommendations") or [])[:3]:
        out.append(
            {
                "title": f"Review {rec['name']} as a diversification theme",
                "detail": rec.get("logic")
                or f"Ranked #{rec.get('rank')} with final score {rec.get('final_score')}.",
                "kind": "sector",
                "source": "rules",
                "basis": "Rule-based sector opportunity scorer (Dhan + Twin exposure)",
            }
        )
    for worry in (analysis_bits.get("top_worries") or [])[:2]:
        out.append(
            {
                "title": worry.get("title") or "Portfolio worry",
                "detail": worry.get("detail") or "",
                "kind": "risk",
                "source": "rules",
                "basis": "Portfolio health / concentration rules from your Twin",
            }
        )
    for cat in (sector_payload.get("high_exposure_categories") or [])[:2]:
        out.append(
            {
                "title": f"Avoid adding more to {cat['name']}",
                "detail": (
                    f"Twin exposure is already ~{cat['exposure_pct']:.1f}%. "
                    "Prefer reviewing underrepresented sectors for new equity capital."
                ),
                "kind": "diversification",
                "source": "rules",
                "basis": "Concentration gate (>25% Twin sector exposure)",
            }
        )
    return out[:8]
