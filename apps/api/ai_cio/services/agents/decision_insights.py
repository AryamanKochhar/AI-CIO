"""Deterministic, detailed decision insights from Twin + preanalysis.

Used by rule-based and LLM analyzers so every Decisions objective gets concrete
observations (concentration, style tilts, AMC overlap, goal fit) without inventing
prices or live market tips.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from domain.decision.contracts import DecisionObjective

ZERO = Decimal("0")


def _dec(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _style_from_name(name: str) -> str:
    n = name.lower()
    if "small cap" in n or "smallcap" in n:
        return "small_cap"
    if "midcap" in n or "mid cap" in n or "emerging" in n:
        return "mid_cap"
    if "large cap" in n or "largecap" in n or "bluechip" in n or "nifty 50" in n:
        return "large_cap"
    if "flexi" in n or "multicap" in n or "multi cap" in n:
        return "flexi_cap"
    if "elss" in n or "tax saver" in n:
        return "elss"
    if "index" in n or "nifty" in n or "sensex" in n:
        return "index"
    if "debt" in n or "liquid" in n or "gilt" in n or "bond" in n:
        return "debt"
    if "hybrid" in n or "balanced" in n:
        return "hybrid"
    return "other"


def _sector_hint_from_name(name: str) -> str | None:
    n = name.upper()
    mapping = [
        (("BANK", "HDFC BANK", "ICICI", "SBI ", "AXIS"), "Financials / Banks"),
        (("PHARMA", "HOSPITAL", "HEALTH"), "Healthcare / Pharma"),
        (("IT ", "INFOSYS", "TCS", "TECH", "SOFTWARE"), "Information Technology"),
        (("AUTO", "MARUTI", "SUZUKI", "TYRE"), "Automobile"),
        (("CEMENT", "JSW CEMENT"), "Cement / Materials"),
        (("CHEMICAL", "SPECIALITY"), "Chemicals"),
        (("TURBINE", "MICROWAVE", "ENGINEERING", "INDUSTRIAL"), "Industrials / Capital Goods"),
        (("RECYCLING", "RESOURCE"), "Metals / Resources"),
        (("NESTLE", "CONSUMER", "FMCG", "PRODUCTS"), "FMCG / Consumer"),
        (("BSE LIMITED", "EXCHANGE"), "Financials / Market Infrastructure"),
    ]
    for tokens, label in mapping:
        if any(tok in n for tok in tokens):
            return label
    return None


def enrich_holding_style_and_sector(holdings: list[dict]) -> list[dict]:
    """Attach heuristic style/sector hints for insight generation (labeled heuristic)."""
    enriched = []
    for h in holdings:
        row = dict(h)
        name = h.get("scheme_name") or h.get("name") or ""
        row["style_hint"] = _style_from_name(name)
        row["sector_hint"] = _sector_hint_from_name(name)
        enriched.append(row)
    return enriched


def build_style_allocation(holdings: list[dict]) -> list[dict[str, Any]]:
    total = sum((_dec(h.get("valuation")) or ZERO for h in holdings), ZERO)
    buckets: dict[str, Decimal] = {}
    for h in holdings:
        style = h.get("style_hint") or _style_from_name(h.get("scheme_name") or "")
        buckets[style] = buckets.get(style, ZERO) + (_dec(h.get("valuation")) or ZERO)
    rows = []
    for style, value in sorted(buckets.items(), key=lambda x: x[1], reverse=True):
        pct = (value / total * Decimal("100")).quantize(Decimal("0.01")) if total > 0 else None
        rows.append(
            {
                "style": style,
                "value": f"{value.quantize(Decimal('0.01'))}",
                "percent": f"{pct}" if pct is not None else None,
                "methodology": "Heuristic from scheme/holding name tokens (not official AMFI category).",
            }
        )
    return rows


def build_sector_hints(holdings: list[dict]) -> list[dict[str, Any]]:
    """Sector weights from NSE classification when present, else name heuristics on equity."""
    equity = [
        h
        for h in holdings
        if h.get("asset_class") == "equity"
        or h.get("amc") == "EQUITY"
        or h.get("instrument_type") == "direct_equity"
    ]
    total = sum((_dec(h.get("valuation")) or ZERO for h in equity), ZERO)
    buckets: dict[str, Decimal] = {}
    for h in equity:
        label = h.get("sector") or h.get("sector_hint") or _sector_hint_from_name(h.get("scheme_name") or h.get("name") or "") or "Unclassified"
        buckets[label] = buckets.get(label, ZERO) + (_dec(h.get("valuation")) or ZERO)
    rows = []
    for sector, value in sorted(buckets.items(), key=lambda x: x[1], reverse=True):
        pct = (value / total * Decimal("100")).quantize(Decimal("0.01")) if total > 0 else None
        rows.append(
            {
                "sector": sector,
                "value": f"{value.quantize(Decimal('0.01'))}",
                "percent": f"{pct}" if pct is not None else None,
                "source": "heuristic_name" if sector != "Unclassified" else "unknown",
            }
        )
    return rows


def build_detailed_insights(
    *,
    twin: dict[str, Any],
    preanalysis: dict[str, Any] | None,
    objective: DecisionObjective | str,
) -> dict[str, Any]:
    """Return rich insights shared across all decision objectives."""
    obj = objective.value if isinstance(objective, DecisionObjective) else str(objective)
    pa = preanalysis or twin.get("preanalysis") or {}
    portfolio = twin.get("portfolio") or {}
    holdings = list(portfolio.get("holdings") or [])
    # Prefer metrics list if present
    metrics = list((pa.get("holding_metrics") or []))
    if metrics and not holdings:
        holdings = [
            {
                "scheme_name": m.get("name"),
                "valuation": m.get("value"),
                "asset_class": "equity" if m.get("instrument_type") == "direct_equity" else "mutual_fund",
                "amc": m.get("amc"),
                "sector": m.get("sector"),
                "instrument_type": m.get("instrument_type"),
            }
            for m in metrics
        ]

    holdings = enrich_holding_style_and_sector(holdings)
    style_alloc = build_style_allocation(holdings)
    sector_hints = pa.get("sector_allocation") or []
    # If sector allocation is only Unknown / empty, use heuristics on equity
    useful_sectors = [s for s in sector_hints if s.get("sector") and s.get("sector") != "Unknown"]
    if not useful_sectors:
        sector_hints = build_sector_hints(holdings)

    conc = pa.get("concentration") or {}
    flags = pa.get("portfolio_flags") or {}
    snap = pa.get("portfolio_snapshot") or {}
    health = pa.get("financial_health") or {}
    goals = (twin.get("goals") or {}).get("items") or pa.get("goals") or []
    behaviour = twin.get("behaviour") or {}

    insight_cards: list[dict[str, str]] = []
    observations: list[str] = []
    actions: list[str] = []
    risks: list[str] = []
    tradeoffs: list[str] = []

    # --- Concentration ---
    largest = conc.get("largest_holding_percent")
    top3 = conc.get("top_3_holdings_percent")
    if largest:
        observations.append(
            f"Your largest single holding is about {largest}% of invested value."
        )
        if flags.get("high_single_holding_concentration") or _dec(largest) and _dec(largest) >= 20:
            insight_cards.append(
                {
                    "type": "concentration",
                    "title": "High single-holding weight",
                    "detail": (
                        f"One position is ~{largest}% of the portfolio. "
                        "That amplifies both upside and drawdown from that name/fund."
                    ),
                    "severity": "high",
                }
            )
            actions.append(
                f"Review trimming or pausing SIPs into the largest holding (~{largest}%) "
                "and redirect new equity money toward underrepresented styles/sectors."
            )
            risks.append("A sharp fall in the largest holding would hit overall portfolio value hard.")

    if top3:
        observations.append(f"Your top 3 holdings together are about {top3}% of invested value.")
        if _dec(top3) and _dec(top3) >= 45:
            insight_cards.append(
                {
                    "type": "concentration",
                    "title": "Top-3 concentration",
                    "detail": f"Top three names/funds are ~{top3}% combined — diversification across holdings is limited.",
                    "severity": "medium",
                }
            )
            actions.append(
                "Spread new investments across additional funds/stocks so the top 3 share can drift lower over time."
            )

    # --- Style tilts (mid/small/large) ---
    for row in style_alloc[:6]:
        style = row["style"]
        pct = row.get("percent")
        if not pct:
            continue
        pct_d = _dec(pct) or ZERO
        if style in {"mid_cap", "small_cap"} and pct_d >= 25:
            insight_cards.append(
                {
                    "type": "style_tilt",
                    "title": f"Heavy {style.replace('_', '-')} exposure (~{pct}%)",
                    "detail": (
                        f"Name-heuristic allocation shows ~{pct}% in {style.replace('_', ' ')} strategies. "
                        "These sleeves are typically more volatile than large-cap/index equity."
                    ),
                    "severity": "high" if pct_d >= 35 else "medium",
                }
            )
            observations.append(f"Style tilt: ~{pct}% appears linked to {style.replace('_', ' ')} funds/names.")
            actions.append(
                f"Consider reviewing whether to add large-cap or broad index equity for balance versus your ~{pct}% {style.replace('_', ' ')} sleeve."
            )
            tradeoffs.append(
                f"Reducing {style.replace('_', ' ')} share may lower volatility but can also reduce higher-growth potential."
            )
        if style == "large_cap" and pct_d >= 50:
            observations.append(f"Large-cap / bluechip-style exposure looks elevated (~{pct}%).")
            actions.append(
                "If goals are long-horizon and capacity allows, review whether a measured mid-cap sleeve is missing — only after emergency buffer and concentration checks."
            )

    # --- Sector tilts ---
    if sector_hints:
        top = sector_hints[0]
        top_pct = _dec(top.get("percent") or top.get("weight_percent"))
        top_name = top.get("sector") or "Unknown"
        if top_pct and top_pct >= 30 and top_name not in {"Unknown", "Unclassified"}:
            insight_cards.append(
                {
                    "type": "sector_tilt",
                    "title": f"Overweight: {top_name} (~{top_pct}%)",
                    "detail": (
                        f"Direct equity sleeve is tilted toward {top_name}. "
                        "Sector concentration can create correlated drawdowns."
                    ),
                    "severity": "high" if top_pct >= 40 else "medium",
                }
            )
            observations.append(f"Sector tilt: {top_name} is about {top_pct}% of classified direct equity.")
            # Suggest underweight sectors from remainder
            under = [s for s in sector_hints[1:] if s.get("sector") not in {"Unknown", "Unclassified"}]
            if under:
                light = under[-1] if len(under) >= 1 else None
                others = ", ".join(s.get("sector", "") for s in under[:3] if s.get("sector"))
                actions.append(
                    f"Because {top_name} is ~{top_pct}% of equity, review diversifying new equity buys toward underrepresented sectors"
                    + (f" (currently lighter: {others})" if others else "")
                    + " rather than adding more of the same theme."
                )
            else:
                actions.append(
                    f"Review diversifying away from {top_name} toward other equity sectors you do not hold, instead of adding more {top_name} exposure."
                )
            risks.append(f"Overweight {top_name} means sector-specific news can move a large part of equity value together.")
            tradeoffs.append(
                f"Cutting {top_name} exposure may reduce sector risk but can underperform if that sector continues to lead."
            )
        elif top_name in {"Unknown", "Unclassified"}:
            observations.append(
                "Sector classification is incomplete for many holdings — sector diversification cannot be judged confidently yet."
            )
            actions.append(
                "Improve holding metadata / sector mapping (or re-sync NSE classifications) before making sector-rotation decisions."
            )

    # --- AMC ---
    amc_pct = conc.get("largest_amc_percent")
    if amc_pct and _dec(amc_pct) and _dec(amc_pct) >= 35:
        observations.append(f"Largest fund-house (AMC) share is about {amc_pct}% of holdings value.")
        actions.append(
            f"Review whether too much mutual-fund money sits with one AMC (~{amc_pct}%); consider diversifying new SIPs across houses."
        )

    # --- Behaviour ---
    if behaviour.get("status") == "known":
        scores = behaviour.get("scores") or {}
        risk = scores.get("risk_score")
        loss = scores.get("loss_aversion_score")
        if risk is not None:
            observations.append(f"Psychometric risk score is {risk} (willingness), separate from financial capacity.")
        if loss is not None and float(loss) >= 60:
            insight_cards.append(
                {
                    "type": "behaviour",
                    "title": "Elevated loss aversion",
                    "detail": "Profile suggests drawdowns may be psychologically costly — volatile mid/small sleeves need a clear buffer plan.",
                    "severity": "medium",
                }
            )
            actions.append(
                "Given higher loss aversion, prioritize emergency cash and avoid adding highly concentrated small/mid bets until buffer and goals are clear."
            )

    # --- Goals / liquidity ---
    if not goals:
        observations.append("No goals on record — horizon-based equity sizing is incomplete.")
        actions.append("Add goals with target dates so equity vs debt/cash decisions can be suitability-checked.")
    else:
        for g in goals[:3]:
            name = g.get("name") or g.get("goal_name") or "Goal"
            horizon = g.get("horizon_years") or g.get("years_remaining")
            observations.append(
                f"Goal '{name}'"
                + (f" (~{horizon}y horizon)" if horizon is not None else "")
                + " should gate how aggressive the equity sleeve is."
            )
            if horizon is not None and float(horizon) <= 3:
                actions.append(
                    f"Near-term goal '{name}' → review keeping a larger cash/debt buffer and limiting fresh aggressive equity adds."
                )

    if health.get("liquid_assets_to_monthly_expenses"):
        observations.append(
            f"Liquid assets cover about {health['liquid_assets_to_monthly_expenses']} months of expenses (when expenses known)."
        )
    if flags.get("missing_finances") or flags.get("low_liquidity"):
        actions.append(
            "Complete or raise the liquidity buffer before increasing equity risk — foundations first."
        )

    # --- Objective-specific framing ---
    decision = "Review concentration, style/sector balance, and suitability before changing the portfolio."
    if obj == DecisionObjective.ALLOCATE_CAPITAL.value or obj == "allocate_capital":
        decision = (
            "Allocate new capital with a bias toward filling underrepresented sleeves "
            "(and avoid adding to already-heavy holdings/sectors)."
        )
        if actions:
            actions.insert(
                0,
                "For new money: prefer underrepresented styles/sectors identified above instead of topping up the largest holding.",
            )
    elif obj in {DecisionObjective.EVALUATE_PORTFOLIO_RISK.value, "evaluate_portfolio_risk"}:
        decision = "Portfolio risk is driven more by concentration and style tilt than by the number of holdings alone."
    elif obj in {DecisionObjective.REVIEW_EQUITY_PORTFOLIO.value, "review_equity_portfolio"}:
        decision = "Equity sleeve decision: address concentration and sector/style imbalance before seeking new high-conviction names."
    elif obj in {DecisionObjective.REVIEW_PORTFOLIO.value, "review_portfolio"}:
        decision = "Portfolio review: rebalance toward diversification gaps while respecting goals and liquidity."

    if not observations:
        observations.append("Limited portfolio analytics available — upload statements and complete finances/goals.")
    if not actions:
        actions.append("Complete Twin data (finances, goals, holdings) to unlock sharper allocation decisions.")
    if not risks:
        risks.append("Acting without full Twin data can misjudge capacity and horizon fit.")
    if not tradeoffs:
        tradeoffs.append(
            "Diversifying away from winners can reduce concentration risk but may lag if those positions keep outperforming."
        )

    return {
        "decision_summary": decision,
        "observations": observations,
        "recommended_actions": actions,
        "risks": risks,
        "tradeoffs": tradeoffs,
        "insight_cards": insight_cards,
        "style_allocation": style_alloc,
        "sector_allocation": sector_hints,
        "snapshot": {
            "holdings": snap.get("number_of_holdings") or len(holdings),
            "total_invested_value": snap.get("total_invested_value"),
            "largest_holding_percent": largest,
            "top_3_holdings_percent": top3,
        },
    }
