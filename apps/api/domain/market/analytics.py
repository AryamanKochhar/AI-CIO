"""Deterministic market analytics from normalized snapshots."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from domain.market.contracts import MarketAnalytics, MarketIndexSnapshot

ZERO = Decimal("0")


def _dec(value) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def _pct_distance(current: Decimal | None, bound: Decimal | None) -> Decimal | None:
    if current is None or bound is None or bound == 0:
        return None
    return ((current - bound) / bound * Decimal("100")).quantize(Decimal("0.01"))


def compute_analytics(
    *,
    sectors: list[MarketIndexSnapshot],
    benchmark: MarketIndexSnapshot | None,
    as_of: datetime | None = None,
    is_stale: bool = False,
) -> MarketAnalytics:
    """Calculate sector ranks, relative performance, and breadth."""
    bench_code = benchmark.index_code if benchmark else "NIFTY 50"
    bench_chg = benchmark.change_percent if benchmark else None

    sector_rows: list[dict] = []
    up = down = flat = 0
    for snap in sectors:
        chg = snap.change_percent
        if chg is None:
            continue
        if chg > ZERO:
            up += 1
        elif chg < ZERO:
            down += 1
        else:
            flat += 1
        rel = None
        if bench_chg is not None:
            rel = (chg - bench_chg).quantize(Decimal("0.01"))
        sector_rows.append(
            {
                "index_code": snap.index_code,
                "index_name": snap.index_name,
                "change_percent": f"{chg:.2f}",
                "relative_to_benchmark": f"{rel:.2f}" if rel is not None else None,
                "current_value": f"{snap.current_value:.2f}" if snap.current_value is not None else None,
                "distance_from_year_high_pct": (
                    f"{_pct_distance(snap.current_value, snap.year_high):.2f}"
                    if _pct_distance(snap.current_value, snap.year_high) is not None
                    else None
                ),
                "distance_from_year_low_pct": (
                    f"{_pct_distance(snap.current_value, snap.year_low):.2f}"
                    if _pct_distance(snap.current_value, snap.year_low) is not None
                    else None
                ),
                "is_stale": snap.is_stale,
            }
        )

    sector_rows.sort(
        key=lambda r: Decimal(r["change_percent"]) if r["change_percent"] else ZERO,
        reverse=True,
    )
    for i, row in enumerate(sector_rows, start=1):
        row["rank"] = i

    total = up + down + flat
    breadth_note = None
    if total > 0:
        if down > up:
            breadth_note = f"Sector breadth is negative: {down} of {total} tracked sector indices are down."
        elif up > down:
            breadth_note = f"Sector breadth is positive: {up} of {total} tracked sector indices are up."
        else:
            breadth_note = f"Sector breadth is mixed: {up} up, {down} down, {flat} flat."

    return MarketAnalytics(
        as_of=as_of or datetime.now(tz=sectors[0].timestamp.tzinfo if sectors else None),
        benchmark_code=bench_code,
        benchmark_change_percent=benchmark.change_percent if benchmark else None,
        sectors=sector_rows,
        breadth={
            "sectors_tracked": total,
            "up": up,
            "down": down,
            "flat": flat,
            "note": breadth_note,
        },
        is_stale=is_stale,
        source="nse",
    )
