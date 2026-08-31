"""Deterministic opportunity detection — not investment recommendations."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from domain.market.contracts import MarketIndexSnapshot, OpportunityCandidate

from ai_cio.settings import (
    OPPORTUNITY_EXPOSURE_THRESHOLD_PCT,
    OPPORTUNITY_RELATIVE_CHANGE_THRESHOLD,
    OPPORTUNITY_SECTOR_CHANGE_THRESHOLD,
)


def _dec(value) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def detect_opportunities(
    *,
    analytics: dict[str, Any],
    sector_exposure: dict[str, Any],
    snapshots: list[MarketIndexSnapshot],
) -> list[OpportunityCandidate]:
    candidates: list[OpportunityCandidate] = []
    bench_chg = _dec(analytics.get("benchmark_change_percent"))
    exposure_by_code = {
        s.get("sector_index_code"): s for s in sector_exposure.get("sectors", []) if s.get("sector_index_code")
    }
    exposure_by_name = {s.get("sector_name", "").lower(): s for s in sector_exposure.get("sectors", [])}

    sector_snaps = [s for s in snapshots if s.category == "sector"]
    for snap in sector_snaps:
        chg = snap.change_percent
        if chg is None:
            continue
        rel = (chg - bench_chg).quantize(Decimal("0.01")) if bench_chg is not None else None
        exp = exposure_by_code.get(snap.index_code) or exposure_by_name.get(snap.index_name.lower())
        exp_pct = _dec(exp.get("weight_percent")) if exp else None
        exp_val = _dec(exp.get("value")) if exp else None

        reasons: list[str] = []
        if abs(float(chg)) >= OPPORTUNITY_SECTOR_CHANGE_THRESHOLD:
            reasons.append("sector_move_threshold")
        if rel is not None and abs(float(rel)) >= OPPORTUNITY_RELATIVE_CHANGE_THRESHOLD:
            reasons.append("relative_move_threshold")
        if exp_pct is not None and float(exp_pct) >= OPPORTUNITY_EXPOSURE_THRESHOLD_PCT:
            reasons.append("material_exposure")

        if not reasons or len(reasons) < 2:
            continue

        severity = "attention" if float(chg) < 0 else "information"
        candidates.append(
            OpportunityCandidate(
                type="sector_move",
                sector_index_code=snap.index_code,
                sector_name=snap.index_name,
                market_move_percent=chg,
                benchmark_move_percent=bench_chg,
                relative_move_percent=rel,
                user_exposure_percent=exp_pct,
                user_exposure_value=exp_val,
                reason_codes=reasons,
                severity=severity,
                index_code=snap.index_code,
            )
        )
    return candidates
