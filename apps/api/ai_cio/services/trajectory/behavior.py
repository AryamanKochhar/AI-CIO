"""Observed investment behavior from transactions (not psychometric inventing)."""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any

from ai_cio.services.trajectory.math_utils import ZERO, d, money


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    raw = str(value).strip()
    # ISO first
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        pass
    # Common CAS formats: DD-MM-YYYY / DD/MM/YYYY
    for sep in ("-", "/"):
        parts = raw[:10].split(sep)
        if len(parts) == 3 and len(parts[0]) <= 2 and len(parts[2]) == 4:
            try:
                d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
                return date(y, m, d)
            except ValueError:
                continue
    return None


def _is_buy(txn: dict[str, Any]) -> bool:
    t = f"{txn.get('transaction_type') or ''} {txn.get('description') or ''}".upper()
    return any(k in t for k in ("PURCHASE", "BUY", "SIP", "CREDIT", "ALLOTMENT", "REINVEST"))


def _is_sell(txn: dict[str, Any]) -> bool:
    t = f"{txn.get('transaction_type') or ''} {txn.get('description') or ''}".upper()
    return any(k in t for k in ("REDEEM", "SELL", "DEBIT", "SWITCH OUT"))


def analyze_behavior(
    transactions: list[dict[str, Any]],
    *,
    holdings: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    txns = [t for t in transactions if _parse_date(t.get("date"))]
    txns.sort(key=lambda t: _parse_date(t.get("date")) or date.min)

    comments: list[str] = []
    components: dict[str, dict[str, Any]] = {}
    missing: list[str] = []

    if len(txns) < 3:
        missing.append("transaction_history")
        return {
            "available": False,
            "status": "insufficient_data",
            "components": {},
            "metrics": {"transaction_count": len(txns)},
            "comments": ["Observed behavior needs more transaction history (fewer than 3 dated transactions)."],
            "missing_data": missing,
            "behavior_score": None,
            "disclaimer": "Observed from transactions only — distinct from psychometric profile answers.",
        }

    buys = [t for t in txns if _is_buy(t)]
    sells = [t for t in txns if _is_sell(t)]

    # Monthly contribution amounts (buys)
    by_month: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for t in buys:
        dt = _parse_date(t.get("date"))
        if not dt:
            continue
        amt = d(t.get("amount")) or ZERO
        if amt <= 0 and t.get("units") and t.get("nav"):
            amt = (d(t.get("units")) or ZERO) * (d(t.get("nav")) or ZERO)
        # CAS payout/credit rows often have units but no rupee amount/NAV —
        # use unit counts as a sparse activity proxy so consistency can still score.
        if amt <= 0 and t.get("units"):
            amt = abs(d(t.get("units")) or ZERO)
        by_month[dt.strftime("%Y-%m")] += abs(amt)

    months = sorted(by_month.keys())
    amounts = [by_month[m] for m in months]
    consistency_score = None
    if len(amounts) >= 3:
        mean = sum(amounts) / Decimal(len(amounts))
        if mean > 0:
            var = sum((a - mean) ** 2 for a in amounts) / Decimal(len(amounts))
            cv = (var ** Decimal("0.5")) / mean
            # Low CV → high consistency
            consistency_score = max(20, min(95, int(95 - float(cv) * 80)))
            components["consistency"] = {
                "score": consistency_score,
                "status": "ok",
                "note": f"Contribution CV across {len(amounts)} active months; lower volatility → higher score.",
            }
            if consistency_score >= 75:
                comments.append(f"Your investments have been fairly consistent across {len(amounts)} months with buy activity.")
            else:
                comments.append("Your contribution amounts vary meaningfully from month to month (observed).")
        else:
            missing.append("buy_amounts")
    else:
        missing.append("monthly_buy_span")
        components["consistency"] = {
            "score": None,
            "status": "insufficient_data",
            "note": "Need buy activity spanning at least 3 months.",
        }

    # Trading frequency
    span_days = 1
    d0 = _parse_date(txns[0].get("date"))
    d1 = _parse_date(txns[-1].get("date"))
    if d0 and d1:
        span_days = max(1, (d1 - d0).days)
    annual_turnover_proxy = (len(sells) + len(buys)) * (365.25 / span_days)
    # Prefer lower churn for long-term score
    freq_score = max(25, min(95, int(100 - annual_turnover_proxy * 3)))
    components["trading_frequency"] = {
        "score": freq_score,
        "status": "ok",
        "note": f"~{annual_turnover_proxy:.1f} buy/sell events per year (proxy).",
    }
    if annual_turnover_proxy > 24:
        comments.append("Observed trading frequency is relatively high versus a long-horizon investor baseline.")
    else:
        comments.append("Observed trading frequency appears relatively moderate/low.")

    # Concentration from holdings
    conc_score = None
    if holdings:
        vals = []
        for h in holdings:
            v = d(h.get("valuation")) or ZERO
            if v > 0:
                vals.append(v)
        if vals:
            total = sum(vals)
            largest = max(vals) / total * 100 if total > 0 else ZERO
            # 10% → 90, 40% → 40
            conc_score = max(15, min(95, int(100 - float(largest) * 1.5)))
            components["concentration_discipline"] = {
                "score": conc_score,
                "status": "ok",
                "note": f"Largest holding ~{largest:.1f}% of valued holdings.",
                "largest_holding_percent": f"{largest.quantize(Decimal('0.01'))}",
            }
            if float(largest) >= 25:
                comments.append("Portfolio has become concentrated in a relatively large single holding (observed).")
    else:
        components["concentration_discipline"] = {
            "score": None,
            "status": "insufficient_data",
            "note": "Holdings required for concentration behavior.",
        }
        missing.append("holdings_for_concentration")

    # Sell vs buy ratio
    if buys:
        sell_ratio = len(sells) / max(1, len(buys))
        comments.append(
            f"Observed {len(buys)} buy-like and {len(sells)} sell-like transactions in available history."
        )
    else:
        sell_ratio = None

    scored = [c["score"] for c in components.values() if c.get("score") is not None]
    behavior_score = int(round(sum(scored) / len(scored))) if scored else None

    return {
        "available": True,
        "status": "ok",
        "behavior_score": behavior_score,
        "components": components,
        "metrics": {
            "transaction_count": len(txns),
            "buy_count": len(buys),
            "sell_count": len(sells),
            "active_buy_months": len(months),
            "span_days": span_days,
            "annual_event_rate": f"{annual_turnover_proxy:.2f}",
            "sell_to_buy_ratio": f"{sell_ratio:.2f}" if sell_ratio is not None else None,
            "monthly_buy_totals": {m: money(by_month[m]) for m in months[-12:]},
        },
        "comments": comments,
        "missing_data": missing,
        "source": "observed_transactions",
        "disclaimer": (
            "Observed behavior from uploaded transactions — separate from psychometric questionnaire answers. "
            "Not a psychological diagnosis."
        ),
    }
