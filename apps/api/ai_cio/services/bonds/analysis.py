"""Bond evidence, explicit product gates and Twin-aware comparative findings."""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timezone
import json
import math
from zoneinfo import ZoneInfo

from ai_cio.services.cashflow_math import monthly_field
from ai_cio.services.bonds.cashflows import bill_metrics, budget_lots, fixed_cashflows, full_price, number, rate_metrics, shift_months
from ai_cio.services.bonds.provider import DhanBondProvider
from ai_cio.services.bonds.terms import load_verified_terms

IST = ZoneInfo("Asia/Kolkata")


def _r(value):
    return round(value, 6) if isinstance(value, (int, float)) and math.isfinite(value) else None


def _stamp(value) -> datetime | None:
    if not isinstance(value, str) or len(value) > 64:
        return None
    for parser in (lambda s: datetime.fromisoformat(s.replace("Z", "+00:00")),
                   lambda s: datetime.strptime(s, "%d/%m/%Y %H:%M:%S")):
        try:
            parsed = parser(value)
            return parsed.replace(tzinfo=IST) if parsed.tzinfo is None else parsed
        except ValueError:
            continue
    return None


def quote_state(raw: dict | None, terms: dict, *, now: datetime, as_of: date) -> dict:
    base = {"price": None, "last_trade_at": None, "quote_status": "unavailable",
            "settlement_date": None, "settlement_verified": False, "best_bid": None,
            "best_ask": None, "spread_pct": None, "ask_quantity": None, "reasons": []}
    if not isinstance(raw, dict):
        return {**base, "reasons": ["No Dhan quote row was returned for this exact security."]}
    price = number(raw.get("last_price"), nonnegative=True)
    trade, fetched = _stamp(raw.get("last_trade_time")), _stamp(raw.get("fetched_at"))
    base.update(price=price if price and price > 0 else None,
                last_trade_at=trade.isoformat() if trade else None)
    if base["price"] is None:
        base["quote_status"] = "invalid"
        base["reasons"].append("The quote has no positive finite last price.")
        return base
    if fetched is None or not 0 <= (now - fetched).total_seconds() <= 300:
        base["quote_status"] = "stale"
        base["reasons"].append("Quote receipt is missing, future-dated or older than five minutes.")
        return base
    if trade is None or trade > now or trade.astimezone(IST).date() > as_of or not 0 <= (now - trade).total_seconds() <= 3 * 86400:
        base["quote_status"] = "stale"
        base["reasons"].append("Last trade is missing, future-dated or older than the three-calendar-day application limit.")
        return base
    depth = raw.get("depth") or {}
    bids, asks = [], []
    if isinstance(depth, dict):
        for side, target in (("buy", bids), ("sell", asks)):
            for level in depth.get(side) or []:
                if not isinstance(level, dict):
                    continue
                p, q = number(level.get("price"), nonnegative=True), number(level.get("quantity"), nonnegative=True)
                if p and q:
                    target.append((p, q))
    if not bids or not asks:
        base["quote_status"] = "price_only"
        base["reasons"].append("Two-sided positive market depth is missing; a last price is not an offer.")
        return base
    bid, ask = max(bids, key=lambda v: v[0]), min(asks, key=lambda v: v[0])
    spread = (ask[0] - bid[0]) / ((ask[0] + bid[0]) / 2) * 100
    base.update(best_bid=bid[0], best_ask=ask[0], ask_quantity=ask[1], spread_pct=_r(spread))
    if spread < 0 or spread > 2:
        base["quote_status"] = "invalid"
        base["reasons"].append("The quote is crossed or exceeds the two-percent application spread limit.")
        return base
    base["quote_status"] = "verified_fresh_depth"
    # Normal Dhan quote responses do not establish an issue's actual settlement
    # date. A separately verified adapter/test may provide this additional fact.
    settlement = raw.get("settlement_date")
    if raw.get("settlement_verified") is True and isinstance(settlement, str):
        try:
            day = date.fromisoformat(settlement)
            if as_of <= day < date.fromisoformat(terms["maturity_date"]):
                base.update(settlement_date=settlement, settlement_verified=True)
        except ValueError:
            pass
    return base


def _context(twin: dict, as_of: date) -> dict:
    behavior = twin.get("behaviour") or {}
    scores = behavior.get("scores") or {}
    risk, loss = number(scores.get("risk_score")), number(scores.get("loss_aversion_score"))
    effective = min(risk, loss) if behavior.get("status") == "known" and all(
        v is not None and 0 <= v <= 100 for v in (risk, loss)) else None
    fp = twin.get("financial_position") or {}
    expenses = monthly_field(fp, "expenses")
    node = fp.get("liquid") or {}
    liquid = number(node.get("value"), nonnegative=True) if isinstance(node, dict) and node.get("known") is not False else None
    reserve_months = number((twin.get("decision_constraints") or {}).get("emergency_reserve_months"), nonnegative=True)
    reserve_months = reserve_months if reserve_months is not None and reserve_months <= 60 else 3.0
    reserve_need = float(expenses) * reserve_months if expenses is not None and expenses > 0 else None
    reserve_ok = liquid is not None and reserve_need is not None and liquid >= reserve_need
    constraints = twin.get("decision_constraints") or {}
    selected = constraints.get("goal_ids") or constraints.get("selected_goal_ids") or []
    if isinstance(selected, str):
        try:
            selected = json.loads(selected) if selected.startswith("[") else selected.split(",")
        except ValueError:
            selected = []
    if not isinstance(selected, list):
        selected = []
    if constraints.get("goal_id") is not None:
        selected = [*selected, constraints["goal_id"]]
    goals = []
    for goal in (twin.get("goals") or {}).get("items") or []:
        if selected and str(goal.get("id")) not in {str(v) for v in selected}:
            continue
        try:
            target = date.fromisoformat(str(goal["target_date"])[:10])
            exact_target = target.isoformat()
            date_basis = "Recorded target_date"
        except (KeyError, TypeError, ValueError):
            horizon = number(goal.get("horizon_years"), nonnegative=True)
            if horizon is None or not 0 < horizon <= 100:
                continue
            target = shift_months(as_of, round(horizon * 12))
            exact_target = None
            date_basis = "Derived planning anchor: analysis date plus the explicitly recorded horizon, rounded to months; not a confirmed spending deadline"
        if target > as_of:
            goals.append({"id": goal.get("id"), "name": goal.get("name") or goal.get("title") or "Recorded goal",
                          "target_date": exact_target, "comparison_date": target.isoformat(), "date_basis": date_basis,
                          "years": (target - as_of).days / 365.25})
    goals.sort(key=lambda row: row["comparison_date"])
    policy = deepcopy(twin.get("contribution_policy") or {})
    shared = number(policy.get("uncommitted_monthly_ceiling"), nonnegative=True)
    assigned = number(constraints.get("bond_allocation_budget"), nonnegative=True)
    if policy.get("earmarks_confirmed") is not True or shared is None or assigned is None or assigned > shared:
        assigned = None
    return {"psychometrics": {"effective_risk_score": effective, "risk_score": risk, "loss_aversion_score": loss,
                              "status": "applied" if effective is not None else "incomplete",
                              "policy": "min(risk_score, adaptive loss_aversion_score), both 0–100. Thresholds are application review policy, not calibrated outcome probabilities."},
            "goals": goals, "reserve": {"liquid": liquid, "monthly_expenses": float(expenses) if expenses is not None else None,
                                         "required_months": reserve_months, "required_amount": reserve_need, "sufficient": reserve_ok,
                                         "policy": "Default three-month reserve is configurable planning policy, not a legal minimum."},
            "shared_policy": policy, "shared_ceiling": shared, "bond_assigned_budget": assigned,
            "gold_allowed": constraints.get("allow_gold") is True,
            "costs": {"fixed": number(constraints.get("bond_fixed_cost"), nonnegative=True),
                      "rate": number(constraints.get("bond_cost_rate"), nonnegative=True)}}


def _product(terms: dict, market: dict, ctx: dict, *, as_of: date, now: datetime) -> dict:
    maturity = date.fromisoformat(terms["maturity_date"])
    route = (market.get("master") or {}).get(terms["isin"])
    quote = quote_state((market.get("quotes") or {}).get(terms["isin"]), terms, now=now, as_of=as_of)
    checks = ["Exact source-backed ISIN and dated official issue terms", "Coupon is separate from current yield and total return"]
    reasons = list(quote["reasons"])
    if maturity <= as_of:
        reasons.append("Contractual maturity is on or before the analysis date.")
    if not isinstance(route, dict) or route.get("category") != terms["category"]:
        reasons.append("The current master did not confirm this exact economic category and routing identity.")
    else:
        checks.append("Exact current Dhan routing identity joined by ISIN")
        if route.get("buy_sell_indicator") != "A":
            reasons.append("Current catalogue does not permit both buy and sell.")
        master_lot = number(route.get("lot_size"), nonnegative=True)
        if master_lot != terms["lot_size"]:
            reasons.append("The current master lot differs from the verified exchange lot.")
    if quote["quote_status"] == "verified_fresh_depth":
        checks.append("Recent trade, recent quote receipt and two-sided depth passed application checks")
    score = ctx["psychometrics"]["effective_risk_score"]
    suitability_reasons = []
    if score is None:
        suitability_reasons.append("Complete the risk and adaptive-loss assessment before a personalized comparison.")
    if not ctx["reserve"]["sufficient"]:
        suitability_reasons.append("Confirm that the liquid reserve covers the selected reserve policy before locking new money.")
    goals = ctx["goals"]
    if not goals:
        suitability_reasons.append("Record a future goal date before evaluating maturity fit.")
    elif len(goals) > 1:
        suitability_reasons.append("Select one goal or confirm joint allocation before personalized product ranking.")
    elif maturity > date.fromisoformat(goals[0]["comparison_date"]):
        suitability_reasons.append("This security matures after the selected goal; an early sale would expose that liability to market and liquidity risk.")
    if terms["category"] == "sovereign_gold":
        if not ctx["gold_allowed"]:
            suitability_reasons.append("Gold exposure has not been selected for this goal; SGB redemption is not fixed in rupees.")
        if score is not None and score < 50:
            suitability_reasons.append("Recorded risk/loss comfort requires review before adding gold-linked exposure.")
    elif terms["category"] == "government_dated" and score is not None and score < 40 and (maturity - as_of).days > 3 * 365:
        suitability_reasons.append("Recorded low drawdown comfort requires review of this long bond's rate sensitivity.")
    reasons.extend(suitability_reasons)
    goal_role = "Reference terms; goal fit is not evaluated without a selected dated goal."
    if len(goals) == 1:
        gap = (date.fromisoformat(goals[0]["comparison_date"]) - maturity).days
        goal_role = (f"Contractual maturity is {gap} days before {goals[0]['name']}; later funding needs an explicit reinvestment plan."
                     if gap >= 0 else f"Contractual maturity is {-gap} days after {goals[0]['name']}; do not rely on an unpriced early exit.")
        if not goals[0]["target_date"]:
            goal_role += " The comparison date is an illustrative anchor from the recorded horizon; confirm the actual spending date."
    if terms["category"] == "sovereign_gold":
        goal_role = "Gold sleeve only: rupee redemption follows gold and cannot promise a fixed nominal goal amount."
    result = {"isin": terms["isin"], "name": terms["name"], "category": terms["category"], "issuer": terms["issuer"],
              "maturity_date": terms["maturity_date"], "maturity_horizon_years": _r((maturity - as_of).days / 365.25),
              "coupon_rate_pct": terms["coupon_rate_pct"], "face_value": terms["face_value"], "lot_size": terms["lot_size"],
              "price": quote["price"], "comparison_price": None, "comparison_price_basis": None,
              "budget_costs": {"fixed": ctx["costs"]["fixed"], "rate": ctx["costs"]["rate"]},
              "last_trade_at": quote["last_trade_at"], "price_basis": terms["price_basis"],
              "quote_status": quote["quote_status"], "eligibility_status": "terms_only", "yield_status": "not_evaluated",
              "ytm_pct": None, "modified_duration": None, "dv01": None, "unit_budget": None, "units": None,
              "estimated_cost": None, "source_ids": list(terms["source_ids"]), "goal_role": goal_role,
              "readiness": {"status": "blocked", "checks": checks, "reasons": reasons}, "terms": deepcopy(terms),
              "market_evidence": quote, "cashflows": [], "metrics": {}}
    cash_outlay = None
    if quote["price"] is not None:
        result["source_ids"].extend(s["id"] for s in market.get("sources") or [] if s["id"] == "bond_dhan_quotes")
    if terms["category"] == "sovereign_gold":
        result["yield_status"] = "gold_linked_not_fixed_ytm"
        result["metrics"]["coupon_per_unit_per_payment"] = terms.get("coupon_per_unit_per_payment")
        if quote["quote_status"] == "verified_fresh_depth" and quote["settlement_verified"] and terms["price_basis"] == "dirty":
            cash_outlay = quote["best_ask"]
    elif quote["settlement_verified"] and quote["quote_status"] == "verified_fresh_depth" and maturity > as_of:
        settlement = date.fromisoformat(quote["settlement_date"])
        try:
            # Compare an observed ask, not a possibly unexecutable last trade.
            ask = quote["best_ask"]
            if terms["category"] == "treasury_bill":
                metrics = bill_metrics(terms["face_value"], ask, settlement, maturity)
                cash_outlay = ask
                result["cashflows"] = [{"date": maturity.isoformat(), "amount": terms["face_value"], "principal": terms["face_value"], "coupon": 0}]
                result["metrics"] = metrics
                # Keep distinct conventions. Do not relabel bill yield as YTM.
                result["yield_status"] = "computed_verified_cashflows"
            else:
                dirty = full_price(ask, terms["price_basis"], terms, settlement)
                cash_outlay = dirty
                metrics = rate_metrics(terms, settlement, dirty)
                result["metrics"] = metrics
                result.update(ytm_pct=_r(metrics["ytm_pct"]), modified_duration=_r(metrics["modified_duration"]), dv01=_r(metrics["dv01"]))
                result["cashflows"] = fixed_cashflows(terms, settlement)
                result["yield_status"] = "computed_verified_cashflows"
            result["metrics"]["cashflow_calendar_basis"] = "Contractual regular dates, not adjusted bank credit dates. Holiday settlement/payment calendar must be checked separately."
        except (ValueError, KeyError, ArithmeticError):
            reasons.append("The verified terms do not support this cashflow/yield calculation.")
    if not quote["settlement_verified"]:
        reasons.append("Actual settlement date has not been independently confirmed; yield and cash amounts are withheld.")
    result["metrics"].update(comparison_ask=quote["best_ask"], comparison_price_basis=terms["price_basis"],
                              settlement_date=quote["settlement_date"], full_unit_cash_outlay=cash_outlay,
                              price_scope="Flat price is observed LTP; comparison_price is full dirty cash per unit from the verified best ask and settlement, used consistently for yield and quantity illustrations.")
    if cash_outlay is not None:
        result.update(comparison_price=cash_outlay, comparison_price_basis="dirty")
    if not reasons:
        result["eligibility_status"] = "eligible_for_comparison"
        result["readiness"]["status"] = "ready"
        checks.append("Twin horizon, willingness, reserve and verified settlement passed comparison gates")
        assigned, costs = ctx["bond_assigned_budget"], ctx["costs"]
        if assigned is not None and costs["fixed"] is not None and costs["rate"] is not None and cash_outlay is not None:
            try:
                quantity = budget_lots(assigned, cash_outlay, terms["lot_size"], fixed_cost=costs["fixed"], cost_rate=costs["rate"])
                if quantity["units"] <= quote["ask_quantity"]:
                    result.update(unit_budget=assigned, units=quantity["units"], estimated_cost=quantity["estimated_cost"])
                    result["budget_basis"] = "Independent alternative illustration within one assigned bond budget, not additive across products or an order."
            except ValueError:
                pass
    elif suitability_reasons and quote["quote_status"] == "verified_fresh_depth":
        result["eligibility_status"] = "suitability_review"
    if maturity <= as_of:
        result["eligibility_status"] = "excluded"
    return result


def _finding(kind, title, detail, action, principles, evidence, source_ids, *, severity="review"):
    return {"id": "bond_" + kind, "type": kind, "title": title, "detail": detail,
            "suggested_action": action, "severity": severity, "principle_ids": principles,
            "evidence": evidence, "source_ids": source_ids}


def analyse_bonds(twin: dict, *, provider=None, as_of: date) -> dict:
    terms = load_verified_terms(as_of=as_of)
    ctx = _context(twin, as_of)
    try:
        market = (provider or DhanBondProvider()).market_snapshot(terms["products"], as_of=as_of)
    except Exception as exc:
        market = {"master": {}, "quotes": {}, "sources": [], "errors": [f"Market adapter unavailable ({type(exc).__name__}); no prices invented."]}
    now = datetime.now(timezone.utc)
    products = [_product(row, market, ctx, as_of=as_of, now=now) for row in terms["products"]]
    holdings, unmapped = [], []
    by_isin = {p["isin"]: p for p in products}
    for holding in (twin.get("portfolio") or {}).get("holdings") or []:
        isin = str(holding.get("isin") or "").strip().upper()
        if isin in by_isin:
            holdings.append({"isin": isin, "name": by_isin[isin]["name"], "category": by_isin[isin]["category"],
                             "quantity": number(holding.get("units") if holding.get("units") is not None else holding.get("quantity"), nonnegative=True),
                             "valuation": number(holding.get("valuation"), nonnegative=True),
                             "valuation_basis": "Recorded holding valuation; not replaced by an unavailable quote", "source": "financial_twin"})
        elif str(holding.get("asset_class") or "").lower() in ("bond", "gsec", "treasury_bill", "sgb", "fixed_income", "government_bond"):
            unmapped.append({"isin": isin or None, "name": holding.get("scheme_name") or "Unmapped debt security",
                             "reason": "Exact issue terms are outside the verified subset; no name-based yield or tax classification."})
    available = bool(products)
    eligible = [deepcopy(p) for p in products if p["eligibility_status"] == "eligible_for_comparison"]
    eligible.sort(key=lambda p: (p["category"] == "sovereign_gold", p["maturity_date"], p["isin"]))
    for rank, product in enumerate(eligible, 1):
        product["priority"] = rank
        product["ranking_basis"] = "Goal/risk/readiness gates first, then earlier contractual maturity; application comparison order, not return or success probability."
    findings = []
    if available and any(p["quote_status"] != "verified_fresh_depth" for p in products):
        count = sum(p["quote_status"] != "verified_fresh_depth" for p in products)
        findings.append(_finding("quote_readiness", "Verify the market offer before choosing a bond",
                                 f"Official terms are available for {len(products)} reference issues; {count} lack a verified fresh two-sided quote. No yield, executable price or entitlement cause is invented.",
                                 "Refresh read-only Dhan evidence and verify the settlement date before comparing an actual offer.",
                                 ["bond_identity", "bond_liquidity"], {"verified_terms_products": len(products), "products_without_verified_quotes": count,
                                                                      "provider_status": market.get("status", "unavailable")},
                                 ["bond_nse_cm_terms"] + [s["id"] for s in market.get("sources") or []]))
    if ctx["goals"] and products:
        goal = ctx["goals"][0]
        rows = [{"isin": p["isin"], "maturity_date": p["maturity_date"],
                 "days_before_goal": (date.fromisoformat(goal["comparison_date"]) - date.fromisoformat(p["maturity_date"])).days}
                for p in products if p["category"] != "sovereign_gold"]
        findings.append(_finding("goal_cashflow_fit", "Match bond maturity to the recorded goal",
                                 f"{goal['name']} uses {goal['comparison_date']} as its comparison date ({goal['date_basis']}). Compare the bill's fixed redemption and the dated bond's contractual maturity against that liability; an early bill maturity still needs reinvestment, and a late bond requires a risky early exit.",
                                 "Select the goal to fund, then compare the verified maturity dates with FD and fund alternatives centrally.",
                                 ["bond_cashflows", "bond_suitability", "bond_duration"], {"goal": goal, "maturity_matches": rows,
                                                                                        "psychometrics": ctx["psychometrics"], "reserve": ctx["reserve"]},
                                 ["bond_gsec_issue_rbi", "bond_tbill_listing", "bond_nse_cm_terms"]))
    gold = next((p for p in products if p["category"] == "sovereign_gold"), None)
    if gold:
        nominal = gold["terms"]["original_nominal_value"]
        coupon_pct = gold["coupon_rate_pct"]
        frequency = gold["terms"]["coupon_frequency"]
        coupon = nominal * coupon_pct / 100 / frequency
        findings.append(_finding("gold_coupon_basis", "Keep SGB gold exposure separate from nominal goal cash",
                                 f"The June 2030 reference SGB pays {coupon_pct:.2f}% on its original ₹{nominal:,.0f} nominal value: ₹{coupon:.4f} per gram per half-year before tax. Its future rupee redemption follows gold, so it cannot promise the same cash outcome as a fixed-principal bill, bond or FD.",
                                 "Review SGB only within an explicitly selected gold sleeve; verify acquisition route and current tax conditions before a transaction.",
                                 ["bond_gold", "bond_price_yield", "bond_tax"], {"isin": gold["isin"], "original_nominal_value": nominal,
                                                                                                          "annual_coupon_pct": coupon_pct, "payments_per_year": frequency,
                                                                                                          "coupon_per_payment": coupon, "maturity_date": gold["maturity_date"],
                                                                                                          "redemption": "gold_linked_not_fixed"}, gold["source_ids"]))
    sources = {s["id"]: deepcopy(s) for s in terms["sources"] + (market.get("sources") or [])}
    errors = list(market.get("errors") or []) + ([terms["error"]] if terms.get("error") else [])
    next_action = ("Refresh the read-only Dhan quote batch and confirm actual settlement; the current response supplies no verified bond offer."
                   if not eligible else "Compare one product against the selected goal and shared budget; confirm total costs before any amount is committed.")
    if products and all(p["quote_status"] == "verified_fresh_depth" for p in products) and not eligible:
        next_action = next((reason for p in products for reason in p["readiness"]["reasons"]),
                           "Confirm the selected goal, settlement date and liquidity reserve before choosing an offer.")
    return {"version": "bond-intelligence-v1", "agent": "bond_agent", "available": available,
            "status": "ready" if eligible else "terms_only" if available else "unavailable", "as_of": as_of.isoformat(),
            "summary": f"{len(products)} source-backed bond terms comparisons; {len(eligible)} pass current quote, settlement and Twin suitability gates. No order is placed.",
            "holdings": holdings, "catalogue_products": products, "eligible_products": eligible,
            "excluded_products": [{"isin": p["isin"], "name": p["name"], "reasons": p["readiness"]["reasons"]}
                                  for p in products if p["eligibility_status"] != "eligible_for_comparison"]
                                 + [{"isin": row["isin"], "name": row["name"], "reasons": [row["reason"]]} for row in unmapped],
            "findings": findings, "sources": list(sources.values()),
            "data_quality": {"next_action": next_action, "provider_status": market.get("status", "unavailable"), "warnings": errors,
                             "verified_catalogue_products": len(products), "eligible_products": len(eligible),
                             "psychometrics": ctx["psychometrics"], "goals": ctx["goals"], "reserve": ctx["reserve"],
                             "unmapped_holdings": unmapped,
                             "tax": "Prospective tax not computed; SGB exemption needs current original-issue-through-maturity conditions and actual lots.",
                             "scope": "Dated terms are actual public evidence, separate from current quotes. Missing offers produce one readiness action, not manufactured prices."},
            "constraint_policy": {**ctx["shared_policy"], "bond_assigned_budget": ctx["bond_assigned_budget"],
                                  "scope": "The shared ceiling is not an additional bond allocation. Product quantities, when supported, are independent alternatives and cannot be added together."},
            "methods": {"terms_version": terms["version"], "terms_sha256": terms["sha256"],
                        "calculations": "Regular option-free 30E/360 coupon cashflows and nominal semiannual YTM; bills use distinct ACT/365F simple annualized investment yield. No SGB fixed YTM.",
                        "calendar": "Coupon/maturity reference dates are contractual and unadjusted; actual holiday payment/settlement timing requires confirmation.",
                        "freshness": "Application policy: quote receipt ≤5 minutes, last trade ≤3 calendar days, positive two-sided depth and spread≤2%; these checks do not guarantee execution.",
                        "amounts": "Withheld until a separately assigned central bond budget, explicit costs, lot/depth and settlement checks pass.",
                        "correlation": "No bond/equity correlation is inferred from price-only, sparse or unavailable histories.",
                        "primary_issues": "No current primary subscription window is asserted from an old catalogue or issue notice."}}
