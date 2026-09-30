"""Trendlyne sector day-change fetch for Decisions equity context.

Uses public sector tree-map JSON. Only passes signed day-change % per sector.
"""
from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from ai_cio import settings

logger = logging.getLogger(__name__)

TRENDLYNE_SECTOR_URL = (
    "https://trendlyne.com/equity/sector-industry-analysis/overall/day-changeP/?format=json"
)
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36"
)

_cache: dict[str, Any] | None = None
_cache_at: float = 0.0


def _ttl_seconds() -> int:
    return max(60, int(getattr(settings, "TRENDLYNE_SECTOR_CACHE_TTL_SECONDS", 300) or 300))


def _enabled() -> bool:
    return bool(getattr(settings, "TRENDLYNE_SECTOR_DAY_CHANGE_ENABLED", True))


def _parse_sectors(payload: dict[str, Any]) -> list[dict[str, Any]]:
    body = payload.get("body") if isinstance(payload, dict) else None
    if not isinstance(body, dict):
        return []
    sector_block = body.get("sector") if isinstance(body.get("sector"), dict) else {}
    chart = sector_block.get("chart") if isinstance(sector_block.get("chart"), list) else []
    rows: list[dict[str, Any]] = []
    for item in chart:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        # param_value is signed; value is absolute magnitude only
        raw = item.get("param_value")
        if raw is None:
            disp = str(item.get("disp_value") or "").replace("%", "").strip()
            try:
                raw = float(disp) if disp else None
            except (TypeError, ValueError):
                raw = None
        try:
            day_change = float(raw) if raw is not None else None
        except (TypeError, ValueError):
            day_change = None
        if day_change is None:
            continue
        rows.append({"name": name, "day_change_percent": round(day_change, 2)})
    rows.sort(key=lambda r: r["day_change_percent"], reverse=True)
    return rows


def fetch_sector_day_changes(*, force: bool = False) -> dict[str, Any]:
    """Return sector day-change % list for LLM / Decisions context."""
    global _cache, _cache_at

    if not _enabled():
        return {
            "available": False,
            "source": "trendlyne",
            "metric": "day_change_percent_mcap_weighted",
            "sectors": [],
            "doing_well": [],
            "doing_poorly": [],
            "reason": "TRENDLYNE_SECTOR_DAY_CHANGE_ENABLED is false",
        }

    now = time.monotonic()
    if not force and _cache is not None and (now - _cache_at) < _ttl_seconds():
        return dict(_cache)

    try:
        with httpx.Client(timeout=20.0, follow_redirects=True) as client:
            resp = client.get(
                TRENDLYNE_SECTOR_URL,
                headers={
                    "User-Agent": _USER_AGENT,
                    "Accept": "application/json",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Referer": "https://trendlyne.com/",
                },
            )
            resp.raise_for_status()
            payload = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("trendlyne_sector_fetch_failed err=%s", exc)
        if _cache is not None:
            stale = dict(_cache)
            stale["stale"] = True
            stale["note"] = "Using cached sector day changes after fetch failure."
            return stale
        return {
            "available": False,
            "source": "trendlyne",
            "metric": "day_change_percent_mcap_weighted",
            "sectors": [],
            "doing_well": [],
            "doing_poorly": [],
            "reason": f"Could not fetch Trendlyne sector day changes: {exc}",
        }

    sectors = _parse_sectors(payload if isinstance(payload, dict) else {})
    doing_well = [s for s in sectors if s["day_change_percent"] > 0][:5]
    doing_poorly = sorted(
        [s for s in sectors if s["day_change_percent"] < 0],
        key=lambda r: r["day_change_percent"],
    )[:5]

    result = {
        "available": bool(sectors),
        "source": "trendlyne",
        "metric": "day_change_percent_mcap_weighted",
        "change_param": "day_changeP_mcapw_sec",
        "sectors": sectors,
        "doing_well": doing_well,
        "doing_poorly": doing_poorly,
        "note": (
            "Intraday/session sector day-change % (mcap-weighted). "
            "Educational market context only — not a buy/sell signal."
        ),
    }
    if not sectors:
        result["reason"] = "Trendlyne response had no sector chart rows."

    _cache = dict(result)
    _cache_at = now
    return result
