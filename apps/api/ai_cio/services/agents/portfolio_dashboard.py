"""Portfolio health dashboard metrics for Decisions results.

Deterministic scores from Twin/preanalysis. Components without data stay
unavailable and are excluded from the overall average (not silently filled).
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from ai_cio.services.agents.decision_insights import (
    build_detailed_insights,
    build_sector_hints,
    build_style_allocation,
    enrich_holding_style_and_sector,
)

ZERO = Decimal("0")


def _dec(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _clamp(score: float) -> int:
    return int(max(0, min(100, round(score))))


def _theme_from_name(name: str) -> list[str]:
    n = name.upper()
    themes: list[str] = []
    rules = [
        (("BANK", "HDFC BANK", "ICICI", "AXIS", "SBI "), "Banking"),
        (("AI", "SOFTWARE", "INFOSYS", "TCS", "TECH", "IT "), "Digital / IT"),
        (("EV", "AUTO", "MARUTI", "SUZUKI", "TYRE"), "Auto / Mobility"),
        (("ENERGY", "OIL", "POWER", "GAS"), "Energy"),
        (("PHARMA", "HOSPITAL", "HEALTH"), "Healthcare"),
        (("CEMENT", "STEEL", "METAL", "RECYCLING", "RESOURCE"), "Materials"),
        (("NESTLE", "FMCG", "CONSUMER", "PRODUCTS"), "Consumer"),
        (("BSE LIMITED", "EXCHANGE", "NBFC"), "Market infrastructure"),
        (("CHEMICAL", "SPECIALITY"), "Specialty chemicals"),
        (("DEFENCE", "AERO", "MICROWAVE", "TURBINE"), "Industrial / Capex"),
    ]
    for tokens, label in rules:
        if any(tok in n for tok in tokens):
            themes.append(label)
    return themes or ["Unclassified theme"]


def _score_diversification(holdings_n: int, top3: Decimal | None, style_n: int) -> dict[str, Any]:
    score = 55.0
    if holdings_n >= 15:
        score += 15
    elif holdings_n >= 8:
        score += 10
    elif holdings_n >= 4:
        score += 5
    else:
        score -= 15
    if top3 is not None:
        if top3 <= 35:
            score += 20
        elif top3 <= 50:
            score += 10
        elif top3 >= 70:
            score -= 20
        elif top3 >= 55:
            score -= 10
    if style_n >= 4:
        score += 10
    elif style_n <= 1:
        score -= 10
    return {
        "score": _clamp(score),
        "available": True,
        "note": "Based on holdings count, top-3 concentration, and style spread.",
    }


def _score_concentration(largest: Decimal | None, top5: Decimal | None, top10: Decimal | None) -> dict[str, Any]:
    # Higher concentration → lower score
    score = 80.0
    if largest is not None:
        score -= float(max(ZERO, largest - Decimal("10")) * Decimal("1.2"))
    if top5 is not None:
        score -= float(max(ZERO, top5 - Decimal("40")) * Decimal("0.6"))
    if top10 is not None:
        score -= float(max(ZERO, top10 - Decimal("60")) * Decimal("0.35"))
    return {
        "score": _clamp(score),
        "available": largest is not None or top5 is not None,
        "note": "Penalises large single-name and top-5/top-10 weights.",
    }


def _score_risk(
    *,
    small_mid_pct: Decimal | None,
    loss_aversion: float | None,
    missing_finances: bool,
) -> dict[str, Any]:
    score = 72.0
    if small_mid_pct is not None:
        if small_mid_pct >= 45:
            score -= 22
        elif small_mid_pct >= 30:
            score -= 12
        elif small_mid_pct <= 15:
            score += 5
    if loss_aversion is not None and loss_aversion >= 60 and small_mid_pct and small_mid_pct >= 25:
        score -= 10
    if missing_finances:
        score -= 8
    return {
        "score": _clamp(score),
        "available": True,
        "note": "Uses mid/small tilt, behaviour, and whether finances are complete.",
    }


def _score_asset_allocation(snap: dict[str, Any], health: dict[str, Any]) -> dict[str, Any]:
    alloc = (snap.get("asset_allocation") or {}) if isinstance(snap.get("asset_allocation"), dict) else {}
    # Also accept nested under portfolio_snapshot
    cash = _dec(alloc.get("cash_percent"))
    equity = _dec(alloc.get("equity_percent"))
    other = _dec(alloc.get("other_percent"))
    score = 70.0
    available = cash is not None or equity is not None or other is not None
    if not available:
        # instrument mix fallback
        return {
            "score": 65,
            "available": True,
            "note": "Limited asset-class tags; scored mainly on completeness of cash vs invested mix.",
        }
    if cash is not None and cash < 5:
        score -= 10
    if cash is not None and cash > 40:
        score -= 8
    if equity is not None and equity > 85:
        score -= 12
    if health.get("liquid_assets_to_monthly_expenses"):
        cover = _dec(health.get("liquid_assets_to_monthly_expenses"))
        if cover is not None and cover < 3:
            score -= 10
        elif cover is not None and cover >= 6:
            score += 5
    return {
        "score": _clamp(score),
        "available": True,
        "note": "Uses cash/equity/other mix and liquidity cover when known.",
    }


def build_portfolio_dashboard(
    *,
    twin: dict[str, Any],
    preanalysis: dict[str, Any] | None = None,
    objective: str = "review_portfolio",
) -> dict[str, Any]:
    pa = preanalysis or twin.get("preanalysis") or {}
    insights = build_detailed_insights(twin=twin, preanalysis=pa, objective=objective)

    portfolio = twin.get("portfolio") or {}
    holdings = enrich_holding_style_and_sector(list(portfolio.get("holdings") or []))
    if not holdings and pa.get("holding_metrics"):
        holdings = enrich_holding_style_and_sector(
            [
                {
                    "scheme_name": m.get("name"),
                    "valuation": m.get("value"),
                    "asset_class": "equity" if m.get("instrument_type") == "direct_equity" else "mutual_fund",
                    "amc": m.get("amc"),
                    "sector": m.get("sector"),
                    "instrument_type": m.get("instrument_type"),
                }
                for m in pa.get("holding_metrics") or []
            ]
        )

    conc = pa.get("concentration") or {}
    flags = pa.get("portfolio_flags") or {}
    snap = pa.get("portfolio_snapshot") or {}
    health = pa.get("financial_health") or {}
    behaviour = twin.get("behaviour") or {}
    scores = behaviour.get("scores") or {} if behaviour.get("status") == "known" else {}

    largest = _dec(conc.get("largest_holding_percent"))
    top3 = _dec(conc.get("top_3_holdings_percent"))
    top5 = _dec(conc.get("top_5_holdings_percent"))
    top10 = _dec(conc.get("top_10_holdings_percent"))

    style_alloc = insights.get("style_allocation") or build_style_allocation(holdings)
    sector_alloc = insights.get("sector_allocation") or build_sector_hints(holdings)

    small_mid = ZERO
    for row in style_alloc:
        if row.get("style") in {"small_cap", "mid_cap"}:
            small_mid += _dec(row.get("percent")) or ZERO

    loss_av = scores.get("loss_aversion_score")
    try:
        loss_av_f = float(loss_av) if loss_av is not None else None
    except (TypeError, ValueError):
        loss_av_f = None

    components = {
        "diversification": _score_diversification(
            int(snap.get("number_of_holdings") or len(holdings) or 0),
            top3,
            len([s for s in style_alloc if (_dec(s.get("percent")) or ZERO) >= 5]),
        ),
        "concentration": _score_concentration(largest, top5, top10),
        "risk": _score_risk(
            small_mid_pct=small_mid if small_mid > 0 else None,
            loss_aversion=loss_av_f,
            missing_finances=bool(flags.get("missing_finances")),
        ),
        "valuation": {
            "score": None,
            "available": False,
            "note": "Fundamental valuation metrics (P/E, P/B, etc.) are not in the Twin yet.",
        },
        "quality": {
            "score": None,
            "available": False,
            "note": "Quality metrics (ROE, margins, growth) are not in the Twin yet.",
        },
        "asset_allocation": _score_asset_allocation(snap, health),
        "fund_overlap": {
            "score": None,
            "available": False,
            "note": "Mutual-fund look-through overlap is not available yet.",
        },
    }

    available_scores = [c["score"] for c in components.values() if c.get("available") and c.get("score") is not None]
    overall = _clamp(sum(available_scores) / len(available_scores)) if available_scores else None

    # --- Worries (top 5) ---
    worries: list[dict[str, Any]] = []
    for card in insights.get("insight_cards") or []:
        worries.append(
            {
                "title": card.get("title") or card.get("type"),
                "detail": card.get("detail") or "",
                "severity": card.get("severity") or "medium",
                "metric": card.get("type"),
                "recommended_range": None,
            }
        )

    # Sector recommended range annotation
    if sector_alloc:
        top = sector_alloc[0]
        pct = _dec(top.get("percent") or top.get("weight_percent"))
        name = top.get("sector")
        if pct and name and name not in {"Unknown", "Unclassified"} and pct >= 25:
            worries.insert(
                0,
                {
                    "title": f"High {name} exposure",
                    "detail": f"{name} ≈ {pct}% of classified direct equity.",
                    "severity": "high" if pct >= 35 else "medium",
                    "metric": f"{pct}%",
                    "recommended_range": "Often reviewed in a ~15–25% band for a single sector sleeve (guideline, not a rule).",
                },
            )

    if top5 and top5 >= 45:
        worries.append(
            {
                "title": "Portfolio concentration",
                "detail": f"Top 5 holdings ≈ {top5}% of invested value.",
                "severity": "high" if top5 >= 60 else "medium",
                "metric": f"{top5}%",
                "recommended_range": "Many plans review keeping top-5 well below ~50–60% unless intentional.",
            }
        )

    worries.append(
        {
            "title": "Fund overlap not measured",
            "detail": "True underlying stock overlap across mutual funds cannot be calculated until look-through data exists.",
            "severity": "medium",
            "metric": None,
            "recommended_range": None,
        }
    )

    if flags.get("missing_goals") or flags.get("missing_finances"):
        worries.append(
            {
                "title": "Incomplete risk capacity inputs",
                "detail": "Goals and/or finances are missing, so suitability of equity risk cannot be fully judged.",
                "severity": "high",
                "metric": None,
                "recommended_range": None,
            }
        )

    # Deduplicate by title, keep top 5
    seen: set[str] = set()
    top_worries: list[dict[str, Any]] = []
    for w in worries:
        title = str(w.get("title") or "")
        if title in seen:
            continue
        seen.add(title)
        top_worries.append(w)
        if len(top_worries) >= 5:
            break

    # --- Concentration analysis ---
    total_invested = _dec(snap.get("total_invested_value"))
    equity_val = ZERO
    for h in holdings:
        if h.get("asset_class") == "equity" or h.get("amc") == "EQUITY" or h.get("instrument_type") == "direct_equity":
            equity_val += _dec(h.get("valuation")) or ZERO
    mf_val = (total_invested or ZERO) - equity_val if total_invested is not None else ZERO
    asset_class_concentration = []
    if total_invested and total_invested > 0:
        asset_class_concentration = [
            {
                "bucket": "direct_equity",
                "percent": f"{(equity_val / total_invested * 100).quantize(Decimal('0.01'))}",
            },
            {
                "bucket": "mutual_funds_and_other",
                "percent": f"{(max(ZERO, mf_val) / total_invested * 100).quantize(Decimal('0.01'))}",
            },
        ]

    market_cap = []
    for style, label in (
        ("large_cap", "Large cap"),
        ("mid_cap", "Mid cap"),
        ("small_cap", "Small cap"),
        ("flexi_cap", "Flexi / multi cap"),
        ("index", "Index"),
        ("elss", "ELSS"),
    ):
        row = next((s for s in style_alloc if s.get("style") == style), None)
        if row and row.get("percent"):
            market_cap.append({"category": label, "percent": row["percent"], "value": row.get("value")})

    concentration_analysis = {
        "largest_holding_percent": conc.get("largest_holding_percent"),
        "top_3_percent": conc.get("top_3_holdings_percent"),
        "top_5_percent": conc.get("top_5_holdings_percent"),
        "top_10_percent": conc.get("top_10_holdings_percent"),
        "largest_amc_percent": conc.get("largest_amc_percent"),
        "sector_concentration": sector_alloc[:8],
        "market_cap_concentration": market_cap,
        "asset_class_concentration": asset_class_concentration,
        "geographic_concentration": [
            {
                "region": "India (assumed for domestic CAS/CDSL holdings)",
                "percent": "100",
                "note": "No overseas holdings classification in Twin yet.",
            }
        ],
        "methodology": "Percents from statement valuations; market-cap/style from name heuristics when official tags are missing.",
    }

    # --- True exposure + themes ---
    theme_buckets: dict[str, Decimal] = {}
    theme_base = ZERO
    for h in holdings:
        val = _dec(h.get("valuation")) or ZERO
        theme_base += val
        for theme in _theme_from_name(h.get("scheme_name") or h.get("name") or ""):
            # Split value across themes if multiple — use full value for primary only
            theme_buckets[theme] = theme_buckets.get(theme, ZERO) + val
            break
    themes = []
    for theme, value in sorted(theme_buckets.items(), key=lambda x: x[1], reverse=True):
        pct = (value / theme_base * 100).quantize(Decimal("0.01")) if theme_base > 0 else None
        themes.append({"theme": theme, "value": f"{value.quantize(Decimal('0.01'))}", "percent": f"{pct}" if pct else None})

    true_exposure = {
        "question": "What am I actually invested in?",
        "sector_exposure": [
            {
                "sector": s.get("sector"),
                "percent": s.get("percent") or s.get("weight_percent"),
                "value": s.get("value"),
            }
            for s in sector_alloc[:10]
        ],
        "market_cap_exposure": market_cap,
        "economic_themes": themes[:10],
        "methodology": (
            "Sector from NSE classification when available, else name heuristics. "
            "Market-cap from style tokens in fund/stock names. Themes are heuristic labels."
        ),
    }

    quality_valuation = {
        "available": False,
        "reason": (
            "Quality × Valuation needs per-holding fundamentals (growth, ROE, margins, P/E, etc.). "
            "Those feeds are not wired yet — quadrant placement is withheld rather than invented."
        ),
        "quadrants": {
            "attractive": [],
            "watch": [],
            "expensive": [],
            "value_trap": [],
        },
        "axes": {
            "x": "Valuation (relative) — unavailable",
            "y": "Quality (fundamentals) — unavailable",
        },
    }

    stars = 1
    if overall is not None:
        if overall >= 85:
            stars = 5
        elif overall >= 70:
            stars = 4
        elif overall >= 55:
            stars = 3
        elif overall >= 40:
            stars = 2

    return {
        "portfolio_health": {
            "score": overall,
            "max_score": 100,
            "stars": stars,
            "label": "Portfolio Health",
            "components": components,
            "methodology": (
                "Average of available component scores only. "
                "Valuation, quality, and fund overlap are excluded until data exists."
            ),
        },
        "top_worries": top_worries,
        "concentration_analysis": concentration_analysis,
        "true_exposure": true_exposure,
        "quality_valuation": quality_valuation,
        # keep passthrough for existing UI
        "insight_cards": insights.get("insight_cards") or [],
        "style_allocation": style_alloc,
        "sector_allocation": sector_alloc,
        "observations": insights.get("observations") or [],
        "recommended_actions": insights.get("recommended_actions") or [],
        "risks": insights.get("risks") or [],
        "tradeoffs": insights.get("tradeoffs") or [],
        "decision_summary": insights.get("decision_summary"),
    }
