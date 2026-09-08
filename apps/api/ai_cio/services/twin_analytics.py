"""Deterministic Twin pre-analysis for later LLM consumption.

Computes only what can be derived from Postgres Twin facts.
Does not invent prices, sectors, fundamentals, MF look-through, or returns.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy.orm import Session

from ai_cio.services.finances import serialize_finances
from ai_cio.services.goals import list_goals, serialize_goal
from ai_cio.services.identity import get_user
from ai_cio.services.portfolio import list_holdings
from ai_cio.services.sector_classification import lookup_sector
from domain.analysis import concentration_metrics, total_value

ZERO = Decimal("0")
Q2 = Decimal("0.01")
Q4 = Decimal("0.0001")

# Align with financial_map insight thresholds where sensible.
SINGLE_HOLDING_FLAG = Decimal("25")
TOP3_SOFT = Decimal("60")
SECTOR_FLAG = Decimal("40")
EQUITY_OF_INVESTED_FLAG = Decimal("70")
LIQUIDITY_MONTHS_FLAG = Decimal("3")
DEBT_TO_INCOME_FLAG = Decimal("40")
GOAL_REMAINING_RATIO_FLAG = Decimal("0.5")


def _dec(value) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _money(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return f"{value.quantize(Q2)}"


def _pct(part: Decimal | None, whole: Decimal | None) -> str | None:
    if part is None or whole is None or whole <= 0:
        return None
    return f"{(part / whole * Decimal('100')).quantize(Q2)}"


def _pct_dec(part: Decimal | None, whole: Decimal | None) -> Decimal | None:
    if part is None or whole is None or whole <= 0:
        return None
    return (part / whole * Decimal("100")).quantize(Q2)


def _is_equity(row: dict) -> bool:
    return row.get("asset_class") == "equity" or row.get("amc") == "EQUITY"


def _clean_equity_name(scheme_name: str | None) -> str | None:
    if not scheme_name:
        return None
    name = scheme_name
    for marker in ("#", " - EQUITY", " – EQUITY"):
        if marker in name:
            name = name.split(marker)[0]
    return name.strip() or scheme_name


def _years_remaining(target_date: str | None) -> float | None:
    if not target_date:
        return None
    try:
        # Accept YYYY-MM-DD or YYYY-MM
        raw = target_date.strip()
        if len(raw) == 7:
            raw = f"{raw}-01"
        target = date.fromisoformat(raw[:10])
    except ValueError:
        return None
    today = datetime.now(timezone.utc).date()
    days = (target - today).days
    return round(days / 365.25, 2)


def build_portfolio_preanalysis(db: Session, user_id: int) -> dict[str, Any]:
    """Build the pre-analysis JSON block for an AI agent."""
    get_user(db, user_id)
    holdings = list_holdings(db, user_id)
    finances = serialize_finances(db, user_id)
    goals = [serialize_goal(row) for row in list_goals(db, user_id)]

    income = _dec(finances.get("income"))
    expenses = _dec(finances.get("expenses"))
    liquid = _dec(finances.get("liquid"))
    liabilities = finances.get("liabilities") or []
    liability_total = sum((_dec(item.get("balance")) or ZERO for item in liabilities), ZERO)
    monthly_emi = sum((_dec(item.get("monthly_payment")) or ZERO for item in liabilities), ZERO)

    equity_rows = [h for h in holdings if _is_equity(h)]
    mf_rows = [h for h in holdings if not _is_equity(h)]

    invested_value = total_value(holdings) if holdings else None
    equity_value = total_value(equity_rows) if equity_rows else ZERO
    mf_value = total_value(mf_rows) if mf_rows else ZERO

    invested_amounts = [_dec(h.get("invested_amount")) for h in holdings]
    known_invested = [v for v in invested_amounts if v is not None]
    total_cost = sum(known_invested, ZERO) if known_invested else None
    # Only sum P/L when we have at least one known invested amount; otherwise null.
    unrealised_parts = [_dec(h.get("unrealised_pl")) for h in holdings]
    known_pl = [v for v in unrealised_parts if v is not None]
    unrealised_pnl = sum(known_pl, ZERO) if known_pl else None
    unrealised_pnl_pct = None
    if unrealised_pnl is not None and total_cost and total_cost > 0:
        unrealised_pnl_pct = (unrealised_pnl / total_cost * Decimal("100")).quantize(Q2)

    cash_for_alloc = liquid if liquid is not None else ZERO
    total_assets = None
    if liquid is not None or invested_value is not None:
        total_assets = cash_for_alloc + (invested_value or ZERO)

    # Asset allocation: cash + direct equity known; MFs go to other until style classified.
    asset_allocation = {
        "equity_percent": _pct(equity_value if equity_rows else None, total_assets),
        "debt_percent": None,  # not classified from holdings today
        "cash_percent": _pct(liquid, total_assets) if liquid is not None else None,
        "gold_percent": None,
        "international_percent": None,
        "other_percent": _pct(mf_value if mf_rows else None, total_assets),
        "methodology": (
            "Percents of total_assets = liquid(if known) + invested holdings. "
            "equity_percent = direct equity only. Mutual funds counted in other_percent "
            "until debt/equity style classification exists. debt/gold/international left null."
        ),
    }

    instrument_allocation = {
        "direct_equity_percent": _pct(equity_value if equity_rows else None, invested_value),
        "mutual_funds_percent": _pct(mf_value if mf_rows else None, invested_value),
        "etf_percent": None,
        "bonds_percent": None,
        "other_percent": None,
        "methodology": "Percents of invested holdings only (excludes cash).",
    }

    conc = concentration_metrics(holdings) if holdings else None
    ranked = sorted(holdings, key=lambda h: h.get("valuation") or ZERO, reverse=True)
    portfolio_total = invested_value or ZERO
    top10 = sum((h.get("valuation") or ZERO for h in ranked[:10]), ZERO)

    # Sector map for direct equity
    sector_buckets: dict[str, Decimal] = {}
    holding_sectors: dict[str, str | None] = {}
    for h in equity_rows:
        isin = h.get("isin") or ""
        sector_info = lookup_sector(db, isin) if isin else None
        label = sector_info["sector_name"] if sector_info else "Unknown"
        holding_sectors[isin or h.get("scheme_name") or ""] = None if label == "Unknown" else label
        sector_buckets[label] = sector_buckets.get(label, ZERO) + (h.get("valuation") or ZERO)

    sector_allocation = []
    direct_eq_total = equity_value if equity_value > 0 else ZERO
    for name, value in sorted(sector_buckets.items(), key=lambda x: x[1], reverse=True):
        sector_allocation.append(
            {
                "sector": name,
                "value": _money(value),
                "percent": _pct(value, direct_eq_total if direct_eq_total > 0 else None),
            }
        )

    largest_sector_pct = None
    if sector_allocation and direct_eq_total > 0:
        # Prefer largest known sector; if only Unknown, still report it.
        largest_sector_pct = sector_allocation[0]["percent"]

    concentration = {
        "largest_holding_percent": (
            f"{conc['largest_holding_percentage'].quantize(Q2)}" if conc else None
        ),
        "top_3_holdings_percent": (
            f"{conc['top_3_percentage'].quantize(Q2)}" if conc else None
        ),
        "top_5_holdings_percent": (
            f"{conc['top_5_percentage'].quantize(Q2)}" if conc else None
        ),
        "top_10_holdings_percent": _pct(top10 if holdings else None, portfolio_total if holdings else None),
        "largest_amc_percent": (
            f"{conc['largest_amc_percentage'].quantize(Q2)}" if conc else None
        ),
        "largest_sector_percent": largest_sector_pct,
        "largest_industry_percent": None,  # industry taxonomy not in DB
        "largest_market_cap_category_percent": None,  # market-cap tags not in DB
        "methodology": (
            "Holding percents use invested portfolio valuation. "
            "Sector percents use direct equity only when NSE classification exists."
        ),
    }

    holding_metrics = []
    for h in ranked:
        val = h.get("valuation") or ZERO
        isin = h.get("isin")
        equity = _is_equity(h)
        sector_label = None
        if equity:
            info = lookup_sector(db, isin) if isin else None
            sector_label = info["sector_name"] if info else None
        holding_metrics.append(
            {
                "symbol": isin,
                "name": _clean_equity_name(h.get("scheme_name")) if equity else h.get("scheme_name"),
                "instrument_type": "direct_equity" if equity else "mutual_fund",
                "amc": h.get("amc"),
                "value": _money(val),
                "portfolio_weight_percent": _pct(val, portfolio_total if portfolio_total > 0 else None),
                "invested_value": _money(_dec(h.get("invested_amount"))),
                "current_value": _money(val),
                "pnl": _money(_dec(h.get("unrealised_pl"))),
                "pnl_percent": (
                    f"{_dec(h.get('unrealised_pl_pct')).quantize(Q2)}"
                    if _dec(h.get("unrealised_pl_pct")) is not None
                    else None
                ),
                "sector": sector_label,
                "industry": None,
                "market_cap_category": None,
                "valuation": {
                    "pe": None,
                    "pb": None,
                    "ev_ebitda": None,
                    "peg": None,
                    "dividend_yield_percent": None,
                },
                "quality": {
                    "revenue_growth_percent": None,
                    "earnings_growth_percent": None,
                    "roe_percent": None,
                    "roce_percent": None,
                    "operating_margin_percent": None,
                    "debt_to_equity": None,
                },
            }
        )

    monthly_surplus = None
    savings_rate = None
    if income is not None and expenses is not None:
        monthly_surplus = income - expenses
        if income > 0:
            savings_rate = (monthly_surplus / income * Decimal("100")).quantize(Q2)

    liquid_cover = None
    if liquid is not None and expenses is not None and expenses > 0:
        liquid_cover = (liquid / expenses).quantize(Q2)

    debt_to_income = None
    if income is not None and income > 0 and monthly_emi > 0:
        debt_to_income = (monthly_emi / income * Decimal("100")).quantize(Q2)

    net_worth = None
    if liquid is not None or invested_value is not None or liability_total > 0:
        net_worth = (liquid or ZERO) + (invested_value or ZERO) - liability_total

    financial_health = {
        "monthly_income": _money(income),
        "monthly_expenses": _money(expenses),
        "monthly_surplus": _money(monthly_surplus),
        "savings_rate_percent": f"{savings_rate}" if savings_rate is not None else None,
        "total_liabilities": _money(liability_total),
        "monthly_emi": _money(monthly_emi),
        "debt_to_income_percent": f"{debt_to_income}" if debt_to_income is not None else None,
        "liquid_assets": _money(liquid),
        "liquid_assets_to_monthly_expenses": f"{liquid_cover}" if liquid_cover is not None else None,
        "net_worth": _money(net_worth),
        "methodology": (
            "surplus = income - expenses; savings_rate = surplus/income; "
            "liquid_assets_to_monthly_expenses = liquid/expenses; "
            "debt_to_income = monthly_emi/income; "
            "net_worth = liquid + invested - liability balances."
        ),
    }

    goal_rows = []
    goal_funding_gap = False
    for g in goals:
        target = _dec(g.get("target_amount"))
        current = _dec(g.get("current_funding"))
        remaining = None
        if target is not None and target > 0:
            remaining = target - (current or ZERO)
            if remaining / target >= GOAL_REMAINING_RATIO_FLAG:
                goal_funding_gap = True
        years = _years_remaining(g.get("target_date"))
        goal_rows.append(
            {
                "goal_name": g.get("name"),
                "goal_type": g.get("goal_type"),
                "target_amount": _money(target),
                "current_amount": _money(current),
                "remaining_amount": _money(remaining),
                "target_date": g.get("target_date"),
                "years_remaining": years,
                "monthly_contribution": None,
                "inflation_assumption_percent": None,
                "expected_return_assumption_percent": None,
                "required_monthly_contribution": None,
                "projected_corpus": None,
                "funding_gap": _money(remaining) if remaining is not None and remaining > 0 else ("0.00" if remaining == 0 else None),
                "priority": g.get("priority"),
            }
        )

    largest_holding = _pct_dec(
        ranked[0].get("valuation") if ranked else None,
        portfolio_total if portfolio_total > 0 else None,
    )
    top3 = _pct_dec(
        sum((h.get("valuation") or ZERO for h in ranked[:3]), ZERO) if ranked else None,
        portfolio_total if portfolio_total > 0 else None,
    )
    equity_of_invested = _pct_dec(equity_value if equity_rows else None, invested_value)

    high_sector = False
    if largest_sector_pct is not None:
        try:
            # Ignore "Unknown" only concentration for the flag when that's the only bucket
            known_sectors = [s for s in sector_allocation if s["sector"] != "Unknown"]
            if known_sectors and Decimal(known_sectors[0]["percent"] or "0") >= SECTOR_FLAG:
                high_sector = True
        except Exception:
            high_sector = False

    largest_equity = None
    if equity_rows and portfolio_total > 0:
        top_eq = max(equity_rows, key=lambda h: h.get("valuation") or ZERO)
        largest_equity = _pct_dec(top_eq.get("valuation"), portfolio_total)

    portfolio_flags = {
        "high_single_holding_concentration": bool(
            largest_holding is not None and largest_holding >= SINGLE_HOLDING_FLAG
        ),
        "high_single_stock_concentration": bool(
            largest_equity is not None and largest_equity >= SINGLE_HOLDING_FLAG
        ),
        "high_top3_concentration": bool(top3 is not None and top3 >= TOP3_SOFT),
        "high_sector_concentration": high_sector,
        "high_industry_concentration": False,  # industry data unavailable
        "high_equity_concentration": bool(
            equity_of_invested is not None and equity_of_invested >= EQUITY_OF_INVESTED_FLAG
        ),
        "low_liquidity": bool(
            liquid_cover is not None and liquid_cover < LIQUIDITY_MONTHS_FLAG
        ),
        "high_debt_burden": bool(
            debt_to_income is not None and debt_to_income >= DEBT_TO_INCOME_FLAG
        ),
        "high_fund_overlap": False,  # look-through unavailable
        "goal_funding_gap": goal_funding_gap,
        "market_cap_concentration": False,  # market-cap tags unavailable
        "missing_finances": income is None and expenses is None and liquid is None,
        "missing_goals": len(goals) == 0,
        "missing_portfolio": len(holdings) == 0,
        "thresholds": {
            "single_holding_percent": str(SINGLE_HOLDING_FLAG),
            "top3_percent": str(TOP3_SOFT),
            "sector_percent": str(SECTOR_FLAG),
            "equity_of_invested_percent": str(EQUITY_OF_INVESTED_FLAG),
            "liquidity_months": str(LIQUIDITY_MONTHS_FLAG),
            "debt_to_income_percent": str(DEBT_TO_INCOME_FLAG),
        },
    }

    return {
        "schema_version": "v1",
        "as_of": datetime.now(timezone.utc).isoformat(),
        "user_id": user_id,
        "portfolio_snapshot": {
            "total_value": _money(total_assets),
            "total_invested_value": _money(invested_value),
            "unrealized_pnl": _money(unrealised_pnl),
            "unrealized_pnl_percent": f"{unrealised_pnl_pct}" if unrealised_pnl_pct is not None else None,
            "number_of_holdings": len(holdings),
            "equity_holdings_count": len(equity_rows),
            "mutual_fund_holdings_count": len(mf_rows),
            "asset_allocation": asset_allocation,
            "instrument_allocation": instrument_allocation,
        },
        "concentration": concentration,
        "sector_allocation": sector_allocation,
        "industry_allocation": [],
        "market_cap_allocation": {
            "large_cap_percent": None,
            "mid_cap_percent": None,
            "small_cap_percent": None,
            "unknown_percent": None,
            "available": False,
            "reason": "Market-cap classification is not stored for holdings yet.",
        },
        "holding_metrics": holding_metrics,
        "overlap": {
            "fund_overlap_available": False,
            "reason": "Mutual-fund look-through holdings are not available yet.",
            "top_overlapping_companies": [],
            "top_overlapping_sectors": [],
        },
        "financial_health": financial_health,
        "goals": goal_rows,
        "portfolio_flags": portfolio_flags,
        "data_gaps": {
            "debt_gold_international_classification": True,
            "industry_classification": True,
            "market_cap_classification": True,
            "fundamentals_valuation_quality": True,
            "fund_lookthrough": True,
            "sector_classification_incomplete": any(
                s["sector"] == "Unknown" for s in sector_allocation
            )
            or (bool(equity_rows) and not any(s["sector"] != "Unknown" for s in sector_allocation)),
        },
    }


# Back-compat alias used in earlier design notes
def build_twin_analytics(db: Session, user_id: int, twin: dict | None = None) -> dict[str, Any]:
    return build_portfolio_preanalysis(db, user_id)
