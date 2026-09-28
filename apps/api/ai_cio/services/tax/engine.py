"""Capital gains summary, loss inventory, and tax opportunities."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from ai_cio.services.tax.lots import build_tax_lots
from ai_cio.services.tax.rules import (
    current_financial_year,
    estimate_equity_tax,
    fy_bounds,
    get_rules,
)

ZERO = Decimal("0")


def _d(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:
        return ZERO


def build_tax_intelligence(
    holdings: list[dict[str, Any]],
    transactions: list[dict[str, Any]],
    *,
    financial_year: str | None = None,
    as_of: date | None = None,
) -> dict[str, Any]:
    as_of = as_of or date.today()
    fy = financial_year or current_financial_year(as_of)
    rules = get_rules(fy)
    fy_start, fy_end = fy_bounds(rules.financial_year)

    lots = build_tax_lots(holdings, transactions, as_of=as_of, financial_year=rules.financial_year)

    stcg = ZERO
    ltcg = ZERO
    stcl = ZERO
    ltcl = ZERO
    realized_gain = ZERO
    realized_loss = ZERO
    by_security: dict[str, dict[str, Any]] = {}

    for row in lots["realized_lots"]:
        sale = date.fromisoformat(row["sale_date"])
        if sale < fy_start or sale > fy_end:
            continue
        g = _d(row["gain_loss"])
        term = row.get("term")
        if g >= 0:
            realized_gain += g
            if term == "short_term":
                stcg += g
            elif term == "long_term":
                ltcg += g
        else:
            realized_loss += abs(g)
            if term == "short_term":
                stcl += abs(g)
            elif term == "long_term":
                ltcl += abs(g)
        name = row["security"]
        bucket = by_security.setdefault(
            name,
            {"security": name, "isin": row.get("isin"), "stcg": ZERO, "ltcg": ZERO, "stcl": ZERO, "ltcl": ZERO},
        )
        if g >= 0 and term == "short_term":
            bucket["stcg"] += g
        elif g >= 0 and term == "long_term":
            bucket["ltcg"] += g
        elif g < 0 and term == "short_term":
            bucket["stcl"] += abs(g)
        elif g < 0 and term == "long_term":
            bucket["ltcl"] += abs(g)

    unrealized_gains = ZERO
    unrealized_losses = ZERO
    for row in lots["unrealized_lots"]:
        g = _d(row["unrealized_gain_loss"])
        if g >= 0:
            unrealized_gains += g
        else:
            unrealized_losses += abs(g)

    tax_est = estimate_equity_tax(stcg=stcg, ltcg=ltcg, stcl=stcl, ltcl=ltcl, rules=rules)

    opportunities = detect_opportunities(
        unrealized_lots=lots["unrealized_lots"],
        stcg=stcg,
        ltcg=ltcg,
        stcl=stcl,
        ltcl=ltcl,
        rules=rules,
        tax_est=tax_est,
    )

    holding_period_events = [
        {
            "type": "holding_period_threshold",
            "security": row["security"],
            "isin": row.get("isin"),
            "days_to_long_term": row.get("days_to_long_term"),
            "unrealized_gain_loss": row.get("unrealized_gain_loss"),
            "current_term": row.get("term"),
            "reason": (
                f"{row['security']} may reach the long-term holding-period threshold "
                f"in approximately {row.get('days_to_long_term')} days under rule {rules.version}. "
                "Selling before vs after the threshold can have different tax consequences."
            ),
            "risks": [
                "Waiting exposes the position to price movement.",
                "Classification depends on accurate acquisition dates.",
            ],
        }
        for row in lots["unrealized_lots"]
        if row.get("term") == "short_term"
        and row.get("days_to_long_term") is not None
        and 0 < int(row["days_to_long_term"]) <= 45
        and _d(row.get("unrealized_gain_loss")) > 0
    ]

    comments = _comments(
        stcg=stcg,
        ltcg=ltcg,
        stcl=stcl,
        ltcl=ltcl,
        unrealized_gains=unrealized_gains,
        unrealized_losses=unrealized_losses,
        opportunities=opportunities,
        holding_period_events=holding_period_events,
        missing=lots["missing_data"],
        tax_est=tax_est,
    )
    alerts = _alerts(
        opportunities=opportunities,
        holding_period_events=holding_period_events,
        stcg=stcg,
        ltcg=ltcg,
        stcl=stcl,
        estimated_tax=_d(tax_est.get("estimated_capital_gains_tax")),
        missing=lots["missing_data"],
    )

    usable = lots["data_quality"].get("usable_cost_lots", 0)
    insuff = lots["data_quality"].get("insufficient", 0) + len(
        [m for m in lots["missing_data"] if m.get("reason") == "missing_acquisition_cost"]
    )
    total_h = max(1, lots["data_quality"].get("total_holdings", 0))
    coverage_pct = int(round(100 * usable / total_h)) if holdings else 0

    has_source = bool(holdings) or bool(transactions)
    usable_ok = usable > 0 or bool(lots["realized_lots"])
    # Honest status: never claim success when we only have holdings with no cost basis.
    if not has_source:
        status = "insufficient_data"
        available = False
    elif not usable_ok and insuff > 0:
        status = "insufficient_data"
        available = True  # data present, but not enough for reliable gain math
    else:
        status = "success"
        available = True
    return {
        "available": available,
        "agent": "tax_agent",
        "status": status,
        "financial_year": rules.financial_year,
        "assessment_year": rules.assessment_year,
        "rule_version": rules.version,
        "as_of": as_of.isoformat(),
        "summary": {
            "stcg": f"{stcg:.2f}",
            "ltcg": f"{ltcg:.2f}",
            "stcl": f"{stcl:.2f}",
            "ltcl": f"{ltcl:.2f}",
            "realized_gains": f"{realized_gain:.2f}",
            "realized_losses": f"{realized_loss:.2f}",
            "unrealized_gains": f"{unrealized_gains:.2f}",
            "unrealized_losses": f"{unrealized_losses:.2f}",
            "estimated_tax": tax_est["estimated_capital_gains_tax"],
            "taxable_gains_estimate": {
                "stcg": tax_est["taxable_stcg"],
                "ltcg_after_exemption": tax_est["taxable_ltcg_after_exemption"],
            },
        },
        "tax_estimate": tax_est,
        "by_security": [
            {
                **{k: (f"{v:.2f}" if isinstance(v, Decimal) else v) for k, v in row.items()},
            }
            for row in sorted(by_security.values(), key=lambda r: r["stcg"] + r["ltcg"], reverse=True)
        ],
        "loss_inventory": {
            "current_year_stcl": f"{stcl:.2f}",
            "current_year_ltcl": f"{ltcl:.2f}",
            "prior_year_stcl": None,
            "prior_year_ltcl": None,
            "carry_forward_history": "unavailable",
            "note": (
                "Prior-year carry-forward history is unavailable from current CAS/CDSL extracts. "
                "Only current-year realized losses from available transactions are shown."
            ),
            "set_off_rules": {
                "stcl_offsets_stcg": rules.stcl_offsets_stcg,
                "stcl_offsets_ltcg": rules.stcl_offsets_ltcg,
                "ltcl_offsets_ltcg_only": rules.ltcl_offsets_ltcg_only,
                "carry_forward_years": rules.carry_forward_years,
            },
        },
        "opportunities": opportunities,
        "holding_period_events": holding_period_events,
        "tax_lots": {
            "realized": lots["realized_lots"][:100],
            "unrealized": lots["unrealized_lots"][:100],
        },
        "data_quality": {
            **lots["data_quality"],
            "coverage_pct": coverage_pct,
            "insufficient_cost_basis_count": insuff,
            "message": (
                f"About {coverage_pct}% of holdings have usable cost information for analytical estimates. "
                f"{insuff} positions need review (often equity without acquisition cost in CDSL)."
            ),
        },
        "missing_data": lots["missing_data"][:50],
        "comments": comments,
        "alerts": alerts,
        "assumptions": list(rules.notes) + list(tax_est.get("assumptions") or []),
        "rules_used": [rules.version],
        "disclaimer": (
            "Analytical estimates based on available transaction data and configured tax-rule version. "
            "This is not tax advice and does not replace a qualified tax professional or ITR filing."
        ),
    }


def detect_opportunities(
    *,
    unrealized_lots: list[dict[str, Any]],
    stcg: Decimal,
    ltcg: Decimal,
    stcl: Decimal,
    ltcl: Decimal,
    rules,
    tax_est: dict[str, Any],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    net_gains = stcg + ltcg
    # Tax-loss harvesting candidates
    losses = sorted(
        [r for r in unrealized_lots if _d(r.get("unrealized_gain_loss")) < 0],
        key=lambda r: _d(r.get("unrealized_gain_loss")),
    )
    for row in losses[:8]:
        loss = abs(_d(row["unrealized_gain_loss"]))
        if loss < 1000:
            continue
        # Rough impact: if ST loss and STCG exists → STCG rate; else LTCG rate on residual
        if stcg > 0:
            impact = (min(loss, stcg) * rules.equity_stcg_rate).quantize(Decimal("0.01"))
        elif ltcg > 0:
            impact = (min(loss, ltcg) * rules.equity_ltcg_rate).quantize(Decimal("0.01"))
        else:
            impact = ZERO
        out.append(
            {
                "type": "tax_loss_harvesting",
                "security": row["security"],
                "isin": row.get("isin"),
                "amount": f"{loss:.2f}",
                "estimated_tax_impact": f"{impact:.2f}",
                "holding_period_days": row.get("holding_days"),
                "term": row.get("term"),
                "confidence": 0.55 if row.get("classification_status") == "ok" else 0.35,
                "reason": (
                    f"Potential tax-loss harvesting opportunity: realizing approximately ₹{loss:.0f} "
                    f"of unrealized loss in {row['security']} may offset eligible capital gains, "
                    f"subject to applicable tax rules and overall portfolio objectives. "
                    f"Estimated illustrative tax impact ≈ ₹{impact:.0f} under {rules.version}."
                ),
                "risks": [
                    "May change portfolio allocation / concentration.",
                    "Transaction costs and re-entry risk are not fully modelled.",
                    "Wash-sale style constraints are not evaluated by this engine.",
                    "Estimated impact is not a guaranteed tax saving.",
                ],
                "label": "Potential tax-loss harvesting opportunity",
            }
        )

    # Gain harvesting vs 112A exemption headroom
    exemption = rules.equity_ltcg_exemption
    used = min(_d(tax_est.get("taxable_ltcg_before_exemption")), exemption)
    headroom = max(ZERO, exemption - used)
    lt_gains = [
        r
        for r in unrealized_lots
        if r.get("term") == "long_term" and _d(r.get("unrealized_gain_loss")) > 5000
    ]
    lt_gains.sort(key=lambda r: _d(r.get("unrealized_gain_loss")), reverse=True)
    if headroom > 0 and lt_gains:
        row = lt_gains[0]
        gain = _d(row["unrealized_gain_loss"])
        candidate = min(gain, headroom)
        out.append(
            {
                "type": "gain_harvesting",
                "security": row["security"],
                "isin": row.get("isin"),
                "amount": f"{candidate:.2f}",
                "threshold": f"{exemption:.2f}",
                "threshold_remaining": f"{headroom:.2f}",
                "estimated_tax_impact": "0.00",
                "confidence": 0.45,
                "reason": (
                    f"Potential gain-harvesting opportunity: realizing approximately ₹{candidate:.0f} "
                    f"of eligible long-term gains in {row['security']} may remain within the configured "
                    f"₹{exemption:.0f} 112A threshold headroom (₹{headroom:.0f} remaining in this estimate), "
                    "subject to your full-year tax position."
                ),
                "risks": [
                    "Threshold is applied at portfolio/year level in this estimate.",
                    "Realizing gains changes market exposure.",
                    "Not tax advice.",
                ],
                "label": "Potential gain-harvesting opportunity",
            }
        )

    if stcl > 0 or ltcl > 0:
        out.append(
            {
                "type": "loss_utilization",
                "security": None,
                "amount": f"{(stcl + ltcl):.2f}",
                "estimated_tax_impact": None,
                "confidence": 0.7,
                "reason": (
                    f"You currently have ₹{stcl:.0f} STCL and ₹{ltcl:.0f} LTCL realized this financial year "
                    "that may be usable against eligible capital gains under configured set-off rules."
                ),
                "risks": [],
                "label": "Existing loss utilization",
            }
        )

    return out


def _comments(**kwargs) -> list[str]:
    stcg = kwargs["stcg"]
    ltcg = kwargs["ltcg"]
    stcl = kwargs["stcl"]
    ltcl = kwargs["ltcl"]
    ug = kwargs["unrealized_gains"]
    ul = kwargs["unrealized_losses"]
    opps = kwargs["opportunities"]
    events = kwargs["holding_period_events"]
    missing = kwargs["missing"]
    tax_est = kwargs["tax_est"]
    out: list[str] = []
    out.append(f"You have ₹{stcg:.0f} of realized STCG this financial year (from available transactions).")
    out.append(f"You have ₹{ltcg:.0f} of realized LTCG this financial year (from available transactions).")
    if ul > 0:
        out.append(
            f"You currently have ₹{ul:.0f} of unrealized losses that may represent potential "
            "tax-loss harvesting opportunities."
        )
    if ug > 0:
        out.append(f"Unrealized gains across positions with usable cost data: ₹{ug:.0f}.")
    if events:
        out.append(f"{len(events)} holding(s) are approaching their long-term holding-period threshold.")
    if stcl > 0:
        out.append(f"You have ₹{stcl:.0f} of STCL potentially available for eligible set-off.")
    if ltcl > 0:
        out.append(f"You have ₹{ltcl:.0f} of LTCL potentially available for eligible set-off against LTCG.")
    out.append(
        f"Estimated capital-gains tax under configured rules: ₹{tax_est['estimated_capital_gains_tax']} "
        "(analytical estimate — not tax advice)."
    )
    cost_missing = [m for m in missing if m.get("reason") == "missing_acquisition_cost"]
    if cost_missing:
        out.append(
            f"Tax analysis is incomplete for {len(cost_missing)} holding(s) because acquisition cost data is missing "
            "(common for equity CDSL extracts)."
        )
    tlh = [o for o in opps if o.get("type") == "tax_loss_harvesting"]
    if tlh:
        out.append(f"{len(tlh)} potential tax-loss harvesting opportunities were identified for review.")
    return out


def _alerts(
    *,
    opportunities: list[dict[str, Any]],
    holding_period_events: list[dict[str, Any]],
    stcg: Decimal,
    ltcg: Decimal,
    stcl: Decimal,
    estimated_tax: Decimal,
    missing: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """In-app tax alerts (deterministic). Link to /tax sections."""
    out: list[dict[str, Any]] = []
    tlh = [o for o in opportunities if o.get("type") == "tax_loss_harvesting"]
    if tlh:
        out.append(
            {
                "type": "tax_loss_harvesting",
                "severity": "info",
                "title": "Tax-loss harvesting opportunity detected",
                "detail": (
                    f"{len(tlh)} potential unrealized-loss candidate(s) for review. "
                    "Estimated impact is illustrative and not a guaranteed tax saving."
                ),
                "href": "/tax#harvesting",
            }
        )
    if holding_period_events:
        out.append(
            {
                "type": "holding_period",
                "severity": "info",
                "title": "Holding-period threshold approaching",
                "detail": (
                    f"{len(holding_period_events)} holding(s) may reach long-term classification soon. "
                    "Selling before vs after can have different tax consequences."
                ),
                "href": "/tax#holding-period",
            }
        )
    if stcg + ltcg >= Decimal("100000"):
        out.append(
            {
                "type": "large_taxable_gain",
                "severity": "warning",
                "title": "Large taxable gain detected",
                "detail": (
                    f"Realized STCG+LTCG this FY ≈ ₹{(stcg + ltcg):.0f} from available transactions "
                    f"(estimated tax ≈ ₹{estimated_tax:.0f})."
                ),
                "href": "/tax#overview",
            }
        )
    if stcl > 0:
        out.append(
            {
                "type": "unused_loss",
                "severity": "info",
                "title": "Unused capital loss available for potential set-off",
                "detail": f"Current-year STCL ≈ ₹{stcl:.0f} may offset eligible gains under configured rules.",
                "href": "/tax#losses",
            }
        )
    cost_missing = [m for m in missing if m.get("reason") == "missing_acquisition_cost"]
    if cost_missing:
        out.append(
            {
                "type": "data_quality",
                "severity": "warning",
                "title": "Tax analysis incomplete for some holdings",
                "detail": (
                    f"{len(cost_missing)} holding(s) lack acquisition cost (common for equity CDSL). "
                    "Those positions are excluded from gain estimates rather than guessed."
                ),
                "href": "/tax#data-quality",
            }
        )
    return out
