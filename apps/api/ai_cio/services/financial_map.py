"""Financial Map view-model — projection of the Digital Financial Twin.

Deterministic nodes, relationships, and insights. No second source of truth.
Does not prescribe investments or fabricate values.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

ZERO = Decimal("0")
TOP_N_HOLDINGS = 8
CONCENTRATION_THRESHOLD = Decimal("0.25")
TOP3_ATTENTION = Decimal("0.60")


def _dec(value) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _money_str(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return f"{value:.2f}"


def _pct(part: Decimal, whole: Decimal) -> Decimal | None:
    if whole <= 0:
        return None
    return (part / whole * Decimal("100")).quantize(Decimal("0.01"))


def build_financial_map(
    *,
    user_name: str,
    income: Decimal | None,
    expenses: Decimal | None,
    liquid: Decimal | None,
    liabilities: list[dict],
    liability_total: Decimal,
    holdings: list[dict],
    goals: list[dict],
    behaviour: dict,
    completeness: dict[str, bool],
    provenance: dict | None,
    portfolio_value: Decimal | None,
) -> dict[str, Any]:
    """Assemble map nodes, edges, allocation, and explainable insights."""
    nodes: list[dict] = []
    edges: list[dict] = []

    equity = [h for h in holdings if h.get("asset_class") == "equity" or h.get("amc") == "EQUITY"]
    mutual_funds = [h for h in holdings if h not in equity]

    equity_value = sum((_dec(h.get("valuation")) or ZERO for h in equity), ZERO)
    mf_value = sum((_dec(h.get("valuation")) or ZERO for h in mutual_funds), ZERO)
    inv_value = equity_value + mf_value
    if portfolio_value is None and inv_value > 0:
        portfolio_value = inv_value

    liquid_v = liquid or ZERO
    total_assets = liquid_v + (portfolio_value or ZERO)
    net_display = total_assets - liability_total

    # --- Root ---
    nodes.append(
        {
            "id": "life",
            "type": "root",
            "label": "Your financial life",
            "subtitle": user_name,
            "value": _money_str(net_display) if (liquid is not None or portfolio_value is not None) else None,
            "value_label": "Estimated net position" if (liquid is not None or portfolio_value is not None) else None,
            "parent_id": None,
            "icon": "life",
            "available": True,
            "child_ids": [],
            "details": {
                "note": "Net position uses recorded liquid assets, investments and liabilities only.",
            },
        }
    )

    def link(parent: str, child: str, kind: str = "contains") -> None:
        edges.append({"from": parent, "to": child, "kind": kind})
        parent_node = next(n for n in nodes if n["id"] == parent)
        parent_node["child_ids"].append(child)

    # --- Cash ---
    cash_id = "cash"
    cash_known = liquid is not None
    nodes.append(
        {
            "id": cash_id,
            "type": "cash",
            "label": "Cash",
            "subtitle": "Liquid savings" if cash_known else "Not available yet",
            "value": _money_str(liquid) if cash_known else None,
            "parent_id": "life",
            "icon": "cash",
            "available": cash_known,
            "child_ids": [],
            "details": {
                "source": "You provided" if cash_known else None,
                "note": None
                if cash_known
                else "AI-CIO doesn't have liquid savings details yet.",
            },
        }
    )
    link("life", cash_id)

    # --- Income / Expenses as informational children of cash (not fabricated accounts) ---
    if income is not None:
        nodes.append(
            {
                "id": "income",
                "type": "income",
                "label": "Income",
                "subtitle": "Recorded inflow",
                "value": _money_str(income),
                "parent_id": cash_id,
                "icon": "income",
                "available": True,
                "child_ids": [],
                "details": {"source": "You provided"},
            }
        )
        link(cash_id, "income", "inflow")
    if expenses is not None:
        nodes.append(
            {
                "id": "expenses",
                "type": "expense",
                "label": "Expenses",
                "subtitle": "Recorded outflow",
                "value": _money_str(expenses),
                "parent_id": cash_id,
                "icon": "expense",
                "available": True,
                "child_ids": [],
                "details": {"source": "You provided"},
            }
        )
        link(cash_id, "expenses", "outflow")

    # --- Investments ---
    inv_id = "investments"
    inv_known = bool(holdings)
    nodes.append(
        {
            "id": inv_id,
            "type": "investments",
            "label": "Investments",
            "subtitle": f"{len(holdings)} holdings" if inv_known else "Not available yet",
            "value": _money_str(portfolio_value) if inv_known else None,
            "parent_id": "life",
            "icon": "investments",
            "available": inv_known,
            "child_ids": [],
            "details": {
                "source": (provenance or {}).get("source") if provenance else None,
                "period_start": (provenance or {}).get("period_start") if provenance else None,
                "period_end": (provenance or {}).get("period_end") if provenance else None,
                "last_processed": (provenance or {}).get("last_processed") if provenance else None,
                "document_id": (provenance or {}).get("document_id") if provenance else None,
                "note": None
                if inv_known
                else "Upload a statement to add investments to your map.",
            },
        }
    )
    link("life", inv_id)

    def add_holding_nodes(parent_id: str, rows: list[dict], prefix: str) -> None:
        ranked = sorted(rows, key=lambda h: _dec(h.get("valuation")) or ZERO, reverse=True)
        visible = ranked[:TOP_N_HOLDINGS]
        overflow = ranked[TOP_N_HOLDINGS:]
        for idx, row in enumerate(visible):
            hid = f"{prefix}-{idx}-{row.get('isin') or row.get('folio') or idx}"
            val = _dec(row.get("valuation"))
            nodes.append(
                {
                    "id": hid,
                    "type": "holding",
                    "label": row.get("scheme_name") or "Holding",
                    "subtitle": row.get("amc") if row.get("amc") != "EQUITY" else (row.get("isin") or "Equity"),
                    "value": _money_str(val),
                    "parent_id": parent_id,
                    "icon": "equity" if parent_id == "equity" else "mutual_fund",
                    "available": True,
                    "child_ids": [],
                    "search_text": " ".join(
                        filter(
                            None,
                            [
                                row.get("scheme_name"),
                                row.get("amc"),
                                row.get("isin"),
                                row.get("folio"),
                            ],
                        )
                    ),
                    "details": {
                        "isin": row.get("isin"),
                        "folio": row.get("folio"),
                        "closing_units": str(row.get("closing_units")) if row.get("closing_units") is not None else None,
                        "nav": _money_str(_dec(row.get("nav"))),
                        "invested_amount": _money_str(_dec(row.get("invested_amount"))),
                        "unrealised_pl": _money_str(_dec(row.get("unrealised_pl"))),
                        "unrealised_pl_pct": str(row.get("unrealised_pl_pct"))
                        if row.get("unrealised_pl_pct") is not None
                        else None,
                        "valuation_date": row.get("valuation_date"),
                        "asset_class": row.get("asset_class") or ("equity" if parent_id == "equity" else "mutual_fund"),
                        "source": row.get("source") or (provenance or {}).get("source"),
                        "document_id": row.get("document_id") or (provenance or {}).get("document_id"),
                        "period_start": (provenance or {}).get("period_start") if provenance else None,
                        "period_end": (provenance or {}).get("period_end") if provenance else None,
                        "last_processed": (provenance or {}).get("last_processed") if provenance else None,
                    },
                }
            )
            link(parent_id, hid)
        if overflow:
            oid = f"{prefix}-more"
            overflow_val = sum((_dec(h.get("valuation")) or ZERO for h in overflow), ZERO)
            nodes.append(
                {
                    "id": oid,
                    "type": "cluster",
                    "label": f"View all {len(ranked)} holdings",
                    "subtitle": f"{len(overflow)} more beyond top {TOP_N_HOLDINGS}",
                    "value": _money_str(overflow_val),
                    "parent_id": parent_id,
                    "icon": "cluster",
                    "available": True,
                    "child_ids": [],
                    "details": {
                        "holdings": [
                            {
                                "label": h.get("scheme_name"),
                                "value": _money_str(_dec(h.get("valuation"))),
                                "isin": h.get("isin"),
                                "folio": h.get("folio"),
                                "amc": h.get("amc"),
                                "nav": _money_str(_dec(h.get("nav"))),
                                "closing_units": str(h.get("closing_units"))
                                if h.get("closing_units") is not None
                                else None,
                                "invested_amount": _money_str(_dec(h.get("invested_amount"))),
                                "unrealised_pl": _money_str(_dec(h.get("unrealised_pl"))),
                                "source": h.get("source") or (provenance or {}).get("source"),
                            }
                            for h in ranked
                        ]
                    },
                    "search_text": " ".join(
                        filter(None, [h.get("scheme_name") or "" for h in overflow])
                    ),
                }
            )
            link(parent_id, oid)

    if equity:
        nodes.append(
            {
                "id": "equity",
                "type": "asset_class",
                "label": "Equity",
                "subtitle": f"{len(equity)} securities",
                "value": _money_str(equity_value),
                "parent_id": inv_id,
                "icon": "equity",
                "available": True,
                "child_ids": [],
                "details": {},
            }
        )
        link(inv_id, "equity")
        add_holding_nodes("equity", equity, "eq")

    if mutual_funds:
        nodes.append(
            {
                "id": "mutual_funds",
                "type": "asset_class",
                "label": "Mutual funds",
                "subtitle": f"{len(mutual_funds)} folios",
                "value": _money_str(mf_value),
                "parent_id": inv_id,
                "icon": "mutual_fund",
                "available": True,
                "child_ids": [],
                "details": {},
            }
        )
        link(inv_id, "mutual_funds")
        add_holding_nodes("mutual_funds", mutual_funds, "mf")

    # --- Goals (no invented allocation links to holdings) ---
    goals_id = "goals"
    goals_known = bool(goals)
    nodes.append(
        {
            "id": goals_id,
            "type": "goals",
            "label": "Goals",
            "subtitle": f"{len(goals)} goals" if goals_known else "Not available yet",
            "value": None,
            "parent_id": "life",
            "icon": "goals",
            "available": goals_known,
            "child_ids": [],
            "details": {
                "note": None
                if goals_known
                else "AI-CIO doesn't have your goals yet.",
                "allocation_note": "Goals are not automatically linked to specific holdings yet.",
            },
        }
    )
    link("life", goals_id)
    for goal in goals:
        gid = f"goal-{goal.get('id')}"
        target = _dec(goal.get("target_amount"))
        funded = _dec(goal.get("current_funding"))
        progress = None
        if target and target > 0 and funded is not None:
            progress = _pct(funded, target)
        nodes.append(
            {
                "id": gid,
                "type": "goal",
                "label": goal.get("name") or "Goal",
                "subtitle": (goal.get("goal_type") or "").replace("_", " ").title() or None,
                "value": _money_str(target),
                "value_label": "Target",
                "parent_id": goals_id,
                "icon": "goal",
                "available": True,
                "child_ids": [],
                "search_text": f"{goal.get('name')} {goal.get('goal_type')}",
                "details": {
                    "target_amount": _money_str(target),
                    "current_funding": _money_str(funded),
                    "progress_pct": str(progress) if progress is not None else None,
                    "target_date": goal.get("target_date"),
                    "source": "You provided",
                    "note": "Investment-to-goal links are not assigned yet — funding shown only when you recorded it.",
                },
            }
        )
        link(goals_id, gid)

    # --- Liabilities ---
    liab_id = "liabilities"
    liab_items = liabilities or []
    liab_known = bool(liab_items) or completeness.get("liabilities", False)
    nodes.append(
        {
            "id": liab_id,
            "type": "liabilities",
            "label": "Liabilities",
            "subtitle": f"{len(liab_items)} recorded" if liab_items else "Not available yet",
            "value": _money_str(liability_total) if liab_items else None,
            "parent_id": "life",
            "icon": "liability",
            "available": bool(liab_items),
            "child_ids": [],
            "details": {
                "note": None
                if liab_items
                else "Liabilities haven't been added yet — net worth may be incomplete.",
            },
        }
    )
    link("life", liab_id)
    for idx, item in enumerate(liab_items):
        lid = f"liability-{idx}"
        bal = _dec(item.get("balance"))
        nodes.append(
            {
                "id": lid,
                "type": "liability",
                "label": item.get("name") or item.get("liability_type") or "Liability",
                "subtitle": item.get("liability_type"),
                "value": _money_str(bal),
                "parent_id": liab_id,
                "icon": "liability",
                "available": True,
                "child_ids": [],
                "search_text": f"{item.get('name')} {item.get('liability_type')}",
                "details": {
                    "balance": _money_str(bal),
                    "monthly_payment": _money_str(_dec(item.get("monthly_payment"))),
                    "source": "You provided",
                },
            }
        )
        link(liab_id, lid)

    # --- Allocation (investments + cash when known) ---
    allocation: list[dict] = []
    basis = total_assets if total_assets > 0 else (portfolio_value or ZERO)
    if basis > 0:
        if cash_known and liquid_v > 0:
            allocation.append(
                {
                    "key": "cash",
                    "label": "Cash",
                    "value": _money_str(liquid_v),
                    "percentage": str(_pct(liquid_v, basis)),
                }
            )
        if equity_value > 0 and (portfolio_value or inv_value) > 0:
            allocation.append(
                {
                    "key": "equity",
                    "label": "Equity",
                    "value": _money_str(equity_value),
                    "percentage": str(_pct(equity_value, basis)),
                }
            )
        if mf_value > 0 and (portfolio_value or inv_value) > 0:
            allocation.append(
                {
                    "key": "mutual_funds",
                    "label": "Mutual funds",
                    "value": _money_str(mf_value),
                    "percentage": str(_pct(mf_value, basis)),
                }
            )

    insights = _build_insights(
        holdings=holdings,
        equity=equity,
        mutual_funds=mutual_funds,
        equity_value=equity_value,
        mf_value=mf_value,
        portfolio_value=portfolio_value or inv_value,
        liquid=liquid,
        expenses=expenses,
        goals=goals,
        completeness=completeness,
        behaviour=behaviour,
        total_assets=total_assets,
        liability_total=liability_total,
    )

    known_flags = [v for v in completeness.values()]
    understood_pct = int(round(100 * sum(1 for v in known_flags if v) / len(known_flags))) if known_flags else 0

    return {
        "root_id": "life",
        "nodes": nodes,
        "edges": edges,
        "allocation": allocation,
        "insights": insights,
        "completeness": {
            "flags": completeness,
            "understood_pct": understood_pct,
        },
        "filters": [
            {"id": "all", "label": "All"},
            {"id": "cash", "label": "Cash"},
            {"id": "equity", "label": "Equity"},
            {"id": "mutual_funds", "label": "Mutual funds"},
            {"id": "goals", "label": "Goals"},
            {"id": "liabilities", "label": "Liabilities"},
        ],
    }


def _build_insights(
    *,
    holdings: list[dict],
    equity: list[dict],
    mutual_funds: list[dict],
    equity_value: Decimal,
    mf_value: Decimal,
    portfolio_value: Decimal,
    liquid: Decimal | None,
    expenses: Decimal | None,
    goals: list[dict],
    completeness: dict[str, bool],
    behaviour: dict,
    total_assets: Decimal,
    liability_total: Decimal,
) -> list[dict]:
    insights: list[dict] = []

    # Data gaps
    if not completeness.get("liabilities"):
        insights.append(
            {
                "id": "gap-liabilities",
                "category": "data_gap",
                "title": "Liabilities not fully known",
                "body": "We don't yet have your liabilities, so net worth may be incomplete.",
                "explore_node_id": "liabilities",
            }
        )
    if not completeness.get("portfolio"):
        insights.append(
            {
                "id": "gap-portfolio",
                "category": "data_gap",
                "title": "Investments not added",
                "body": "Upload a statement to place holdings on your financial map.",
                "explore_node_id": "investments",
            }
        )
    if not completeness.get("goals"):
        insights.append(
            {
                "id": "gap-goals",
                "category": "data_gap",
                "title": "Goals not added",
                "body": "Adding goals helps you see what your money is working toward.",
                "explore_node_id": "goals",
            }
        )

    if portfolio_value > 0 and holdings:
        ranked = sorted(holdings, key=lambda h: _dec(h.get("valuation")) or ZERO, reverse=True)
        top = ranked[0]
        top_val = _dec(top.get("valuation")) or ZERO
        share = _pct(top_val, portfolio_value)
        if share is not None and share >= CONCENTRATION_THRESHOLD * 100:
            insights.append(
                {
                    "id": "concentration-top",
                    "category": "attention",
                    "title": "Concentration worth reviewing",
                    "body": (
                        f"Your largest holding represents {share}% of your investment portfolio"
                        f" ({top.get('scheme_name')})."
                    ),
                    "explore_node_id": "investments",
                }
            )
        top3 = ranked[:3]
        top3_val = sum((_dec(h.get("valuation")) or ZERO for h in top3), ZERO)
        top3_share = _pct(top3_val, portfolio_value)
        if top3_share is not None and top3_share >= TOP3_ATTENTION * 100:
            insights.append(
                {
                    "id": "concentration-top3",
                    "category": "information",
                    "title": "Portfolio concentration",
                    "body": f"Your top 3 holdings represent {top3_share}% of your investment value.",
                    "explore_node_id": "investments",
                }
            )

        # Asset allocation tilt
        if equity_value + mf_value > 0:
            eq_share = _pct(equity_value, equity_value + mf_value)
            mf_share = _pct(mf_value, equity_value + mf_value)
            if eq_share is not None and eq_share >= 70:
                insights.append(
                    {
                        "id": "allocation-equity",
                        "category": "information",
                        "title": "Asset allocation",
                        "body": f"Your investments are heavily concentrated in equity ({eq_share}%).",
                        "explore_node_id": "equity" if equity else "investments",
                    }
                )
            elif mf_share is not None and mf_share >= 70:
                insights.append(
                    {
                        "id": "allocation-mf",
                        "category": "information",
                        "title": "Asset allocation",
                        "body": f"Mutual funds make up {mf_share}% of your investment portfolio.",
                        "explore_node_id": "mutual_funds" if mutual_funds else "investments",
                    }
                )

        # AMC concentration (MF only)
        amc_totals: dict[str, Decimal] = {}
        for h in mutual_funds:
            amc = h.get("amc") or "Unknown"
            amc_totals[amc] = amc_totals.get(amc, ZERO) + (_dec(h.get("valuation")) or ZERO)
        if amc_totals and mf_value > 0:
            top_amc, top_amc_val = max(amc_totals.items(), key=lambda x: x[1])
            amc_share = _pct(top_amc_val, mf_value)
            if amc_share is not None and amc_share >= 40 and len(amc_totals) > 1:
                insights.append(
                    {
                        "id": "concentration-amc",
                        "category": "attention",
                        "title": "Fund house concentration",
                        "body": f"{amc_share}% of your mutual fund value is with {top_amc}.",
                        "explore_node_id": "mutual_funds",
                    }
                )

    # Liquidity — only with liquid + expenses
    if liquid is not None and expenses is not None and expenses > 0:
        months = (liquid / expenses).quantize(Decimal("0.1"))
        insights.append(
            {
                "id": "liquidity-cover",
                "category": "information",
                "title": "Liquidity coverage",
                "body": (
                    f"Your readily available cash covers approximately {months} months "
                    "of recorded expenses."
                ),
                "explore_node_id": "cash",
            }
        )
    elif liquid is not None and expenses is None:
        insights.append(
            {
                "id": "liquidity-unknown",
                "category": "data_gap",
                "title": "Liquidity coverage",
                "body": "Liquidity coverage cannot be assessed yet — expenses are not recorded.",
                "explore_node_id": "cash",
            }
        )

    if liquid is not None and total_assets > 0:
        liq_share = _pct(liquid, total_assets)
        if liq_share is not None:
            insights.append(
                {
                    "id": "liquidity-share",
                    "category": "information",
                    "title": "Cash as a share of assets",
                    "body": f"Your recorded liquid assets represent {liq_share}% of total financial assets we know about.",
                    "explore_node_id": "cash",
                }
            )

    # Goal funding facts only
    for goal in goals:
        target = _dec(goal.get("target_amount"))
        funded = _dec(goal.get("current_funding"))
        if target and funded is not None:
            progress = _pct(funded, target)
            horizon = goal.get("target_date")
            body = (
                f"Your {goal.get('name')} goal currently has ₹{_money_str(funded)} of identified funding"
                f" toward a ₹{_money_str(target)} target"
            )
            if progress is not None:
                body += f" ({progress}%)."
            else:
                body += "."
            if horizon:
                body += f" Target date: {horizon}."
            insights.append(
                {
                    "id": f"goal-cover-{goal.get('id')}",
                    "category": "information",
                    "title": "Goal funding",
                    "body": body,
                    "explore_node_id": f"goal-{goal.get('id')}",
                }
            )

    # Behavioural context — careful, no suitability claim
    if behaviour.get("status") == "known" and portfolio_value > 0 and equity_value > 0:
        observations = behaviour.get("observations") or []
        loss_sensitive = any(
            "loss" in o.lower() or "cautious" in o.lower() or "security" in o.lower()
            for o in observations
        )
        eq_share = _pct(equity_value, portfolio_value)
        if loss_sensitive and eq_share is not None and eq_share >= 50:
            insights.append(
                {
                    "id": "behaviour-context",
                    "category": "information",
                    "title": "Behavioural context",
                    "body": (
                        "Your behavioural profile includes notes about sensitivity to losses, "
                        f"and equity currently represents {eq_share}% of investments. "
                        "This is an observation only — risk capacity and full suitability "
                        "are not assessed here."
                    ),
                    "explore_node_id": "investments",
                }
            )

    if completeness.get("psychometric") and completeness.get("portfolio") and completeness.get("goals"):
        insights.append(
            {
                "id": "positive-foundation",
                "category": "positive",
                "title": "Strong foundation",
                "body": "Behaviour, investments and goals are on your map — a solid base for future guidance.",
                "explore_node_id": "life",
            }
        )

    if liability_total > 0 and total_assets > 0:
        insights.append(
            {
                "id": "liabilities-present",
                "category": "information",
                "title": "Liabilities on record",
                "body": f"Recorded liabilities total ₹{_money_str(liability_total)}.",
                "explore_node_id": "liabilities",
            }
        )

    return insights
