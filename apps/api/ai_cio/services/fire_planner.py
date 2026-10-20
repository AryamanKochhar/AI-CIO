"""Deterministic FIRE scenarios grounded in consent, capacity and declared risk.

This is an inspectable planning comparison, not an execution engine or an India
safe-withdrawal-rate study. Every candidate uses the same user-selected return
scenario: the engine never awards a higher assumed return for taking more risk.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
import json
from pathlib import Path

from ai_cio import settings
from ai_cio.api.schemas import FirePlanningInputs
from ai_cio.psychometrics.polarity import DIMENSION_POLARITY
from ai_cio.services.cashflow_math import monthly_field
from ai_cio.services.skill_principles import applied_principles

ZERO = Decimal(0)
ONE = Decimal(1)
HUNDRED = Decimal(100)
PRINCIPLES = ["fire_spending", "fire_withdrawal", "fire_contribution", "fire_risk", "fire_fd", "fire_joint", "fire_review"]


def _money(value: Decimal | None) -> str | None:
    return None if value is None else str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _number(value) -> Decimal | None:
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        out = Decimal(str(value))
    except Exception:
        return None
    return out if out.is_finite() else None


def _projection(assets: Decimal, target: Decimal, contribution: Decimal | None,
                annual_rate: Decimal, months: int) -> dict:
    # Effective annual return -> equivalent monthly return, end-of-month payment.
    monthly_rate = (ONE + annual_rate / HUNDRED) ** (ONE / Decimal(12)) - ONE
    growth = (ONE + monthly_rate) ** months
    factor = Decimal(months) if monthly_rate == ZERO else (growth - ONE) / monthly_rate
    assets_future = assets * growth
    required = max(target - assets_future, ZERO) / factor
    projected = None if contribution is None else assets_future + contribution * factor
    return {"monthly_rate": monthly_rate, "growth": growth, "annuity_factor": factor,
            "assets_future": assets_future, "required": required, "projected": projected,
            "gap": None if projected is None else max(target - projected, ZERO)}


def _preferences(twin: dict, years: int, expenses: Decimal | None) -> tuple[dict, int, Decimal | None]:
    behaviour = twin.get("behaviour") or {}
    raw = behaviour.get("scores") or {}
    scores = {spec["profile_key"]: _number(raw.get(spec["profile_key"])) for spec in DIMENSION_POLARITY.values()}
    scores = {key: val if val is not None and 0 <= val <= 100 else None for key, val in scores.items()}
    complete = behaviour.get("status") == "known" and all(scores[k] is not None for k in ("risk_score", "loss_aversion_score"))
    effective = min(scores["risk_score"], scores["loss_aversion_score"]) if complete else None
    why = []
    if complete:
        why.append("The lower of declared risk willingness and drawdown comfort bounds the preference target; the funding gap cannot raise it.")
        why.append("Higher loss_aversion_score means more adaptive loss sensitivity in this questionnaire; a lower score lowers the equity preference.")
        if scores["decision_stability_score"] is not None and scores["decision_stability_score"] < 35:
            effective = min(effective, Decimal(39))
            why.append("Low decision stability limits the illustrative mix to the stability-led preference band and adds a written review rule.")
    else:
        why.append("Risk willingness and drawdown comfort must both be recorded before selecting a personalised allocation.")
    capacity_cap = 20 if years <= 5 else 50 if years <= 10 else 70
    why.append(f"The application horizon policy caps illustrative equity at {capacity_cap}% for a {years}-year accumulation horizon; this is not a regulator-prescribed allocation.")
    fp = twin.get("financial_position") or {}
    liquid_node = fp.get("liquid") or {}
    liquid = _number(liquid_node.get("value")) if isinstance(liquid_node, dict) and liquid_node.get("known") is not False else None
    if liquid is None or expenses is None or liquid < expenses * 3:
        capacity_cap = min(capacity_cap, 20)
        why.append("Unverified or less than three months of recorded liquid-expense cover limits illustrative equity to 20%; three months is a configurable application review policy, not proof that reserves are adequate.")
    target = None if effective is None else Decimal(0 if effective < 20 else 20 if effective < 40 else 50 if effective < 70 else 70)
    controls = []
    for key, rule in (
        ("anchoring_score", "Compare future cashflows, access and costs rather than an old purchase price before any rebalance."),
        ("recency_bias_score", "Use a scheduled quarterly implementation review; recent winning returns do not change the entered long-term scenario."),
        ("herding_score", "Write an independent product rationale and verify the official terms before following a popular recommendation."),
        ("overconfidence_score", "Keep the FIRE allocation in diversified buckets; a belief in beating the market does not increase its risk cap."),
        ("decision_stability_score", "Write the allocation and contribution rule before booking and review material changes deliberately."),
    ):
        score = scores.get(key)
        controls.append({"score_key": key, "score": float(score) if score is not None else None,
                         "status": "not_evaluated" if score is None else "applied" if score < 35 else "no_extra_control",
                         "rule": rule, "threshold_basis": "Application review threshold below 35/100; higher scores are more adaptive on this instrument. Not a validated clinical cutoff."})
    return {"status": "applied" if complete else "missing", "scores": {k: float(v) if v is not None else None for k, v in scores.items()},
            "provenance": behaviour.get("provenance") or {}, "source": behaviour.get("source"),
            "polarity": {name: dict(spec) for name, spec in DIMENSION_POLARITY.items()},
            "effective_risk_score": float(effective) if effective is not None else None,
            "policy": "FIRE application policy v1: preference bands <20:0% equity, 20..<40:20%, 40..<70:50%, >=70:70%; effective score is min(risk, adaptive loss score), capped at 39 when stability<35. Horizon and liquidity caps apply independently. No mix is risk-free; scores are declared preferences, not validated return forecasts.",
            "why": why, "implementation_controls": controls}, capacity_cap, target


def _plans(target: Decimal | None, cap: int, contribution: Decimal | None) -> tuple[list[dict], dict | None]:
    plans = []
    for identifier, label, equity, fd, debt in (
        ("preservation", "Capital-stability preference", 0, 80, 20),
        ("stability", "Stability-led accumulation", 20, 60, 20),
        ("balanced", "Balanced accumulation", 50, 30, 20),
        ("growth", "Growth-tilted accumulation", 70, 10, 20),
    ):
        eligible = equity <= cap
        amounts = {"equity": None, "fd": None, "high_quality_debt": None}
        if contribution is not None:
            # The last bucket absorbs cents so displayed amounts sum exactly.
            eq = Decimal(_money(contribution * equity / HUNDRED))
            deposit = Decimal(_money(contribution * fd / HUNDRED))
            amounts = {"equity": _money(eq), "fd": _money(deposit), "high_quality_debt": _money(contribution - eq - deposit)}
        plans.append({"id": identifier, "label": label, "rank": 0, "equity_percent": equity, "fd_percent": fd,
                      "high_quality_debt_percent": debt, "monthly_amounts": amounts,
                      "ranking_evidence": {"preference_target_equity_percent": float(target) if target is not None else None,
                                           "capacity_max_equity_percent": cap, "preference_distance": float(abs(Decimal(equity) - target)) if target is not None else None,
                                           "eligible": eligible},
                      "why": ["Within the horizon/liquidity application cap." if eligible else "Excluded by the horizon/liquidity application cap.",
                              "Broad diversified equity exposure, callable eligible bank-deposit comparisons and high-quality debt are illustrative buckets; product fees, taxation, credit and liquidity need review.",
                              "The same entered return scenario is used for every mix; this ranking does not predict that one mix will earn more."]})
    plans.sort(key=lambda p: (not p["ranking_evidence"]["eligible"], p["ranking_evidence"]["preference_distance"] if target is not None else p["equity_percent"], p["equity_percent"]))
    for rank, plan in enumerate(plans, 1):
        plan["rank"] = rank
    recommended = plans[0] if target is not None and contribution is not None and contribution > ZERO else None
    return plans, recommended


def _fd_options(twin: dict, recommendation: dict | None, as_of: date, current_age: int) -> tuple[list[dict], list[str]]:
    path = Path(settings.ROOT) / "knowledge" / "fd_rate_catalog.json"
    try:
        catalog = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, TypeError):
        return [], ["Verified FD quote catalogue unavailable; no bank rate was invented."]
    if not isinstance(catalog, dict) or not isinstance(catalog.get("products"), list):
        return [], ["Verified FD quote catalogue has an invalid structure; no bank rate was invented."]
    allocation = (recommendation or {}).get("monthly_amounts", {}).get("fd")
    fp = twin.get("financial_position") or {}
    fdnode = fp.get("fixed_deposits") or {}
    all_known = fdnode.get("known") is True
    items = fdnode.get("items") or []
    result, warnings = [], []
    for product in catalog.get("products", []):
        if not isinstance(product, dict):
            warnings.append("An invalid FD catalogue row was excluded.")
            continue
        numeric_rate = _number(product.get("annual_rate_percent"))
        minimum = _number(product.get("min_amount"))
        tenor = _number(product.get("tenor_months"))
        if numeric_rate is None or not 0 <= numeric_rate <= 30 or minimum is None or minimum <= 0 or tenor is None or tenor != tenor.to_integral_value() or not 1 <= tenor <= 120:
            warnings.append("An FD quote with unverified rate, minimum or tenor was excluded.")
            continue
        try:
            verified = date.fromisoformat(product["verified_on"])
            effective = date.fromisoformat(product["effective_from"])
            status = "future_dated" if verified > as_of or effective > as_of else "stale" if (as_of - verified).days > 7 else "current_snapshot"
        except (KeyError, ValueError, TypeError):
            status = "invalid_date"
        if product.get("status") != "verified":
            status = "unverified"
        bank = str(product.get("bank", ""))
        matching = [row for row in items if str(row.get("bank_name", "")).casefold() == bank.casefold()]
        principals = [_number(row.get("principal")) for row in matching]
        existing = sum(principals, ZERO) if all_known and matching and all(n is not None and n >= 0 for n in principals) else None
        senior = current_age >= int(product.get("senior_min_age", 60))
        # Age alone never establishes residency or product eligibility.
        rate = float(numeric_rate) if status == "current_snapshot" else None
        current_allocation = allocation if status == "current_snapshot" else None
        setaside = _number(current_allocation)
        row = {**product, "monthly_allocation": current_allocation,
               "allocation_basis": "Alternative ways to implement the same FD bucket, not additive instructions. Accumulate the monthly set-aside before a one-time eligible deposit; this is not a recurring deposit contract.",
               "review_status": "compare_current_terms" if status == "current_snapshot" else "refresh_quote_before_comparison",
               "quote_status": status, "existing_bank_principal": _money(existing),
               "senior_age_met": senior, "comparison_rate_percent": rate,
               "months_to_minimum_booking": int((minimum / setaside).to_integral_value(rounding="ROUND_CEILING")) if setaside is not None and setaside > 0 else None,
               "rate_application": "General-resident quoted rate shown for comparison only. Senior rate requires age plus bank eligibility confirmation. Future monthly bookings and renewals earn unknown future rates.",
               "insurance_review": "DICGC eligibility and aggregation in the same right and capacity must be confirmed for this bank, across principal plus accrued interest. ₹5 lakh is not a per-FD allowance; no insured amount is inferred from incomplete account records."}
        if existing is not None and existing >= Decimal(500000):
            row["review_status"] = "review_existing_bank_exposure_before_adding"
        result.append(row)
    return result, warnings


def build_fire_plan(twin: dict, planning_inputs: dict | FirePlanningInputs, *, as_of: date | str | None = None) -> dict:
    inputs = planning_inputs if isinstance(planning_inputs, FirePlanningInputs) else FirePlanningInputs.model_validate(planning_inputs)
    values = inputs.model_dump(mode="json")
    today = date.fromisoformat(as_of) if isinstance(as_of, str) else as_of or datetime.now(timezone(timedelta(hours=5, minutes=30))).date()
    years = inputs.retirement_age - inputs.current_age
    months = years * 12
    spending = Decimal(str(inputs.monthly_spending_today))
    inflation = Decimal(str(inputs.inflation_percent))
    rate = Decimal(str(inputs.accumulation_return_percent))
    withdrawal = Decimal(str(inputs.withdrawal_rate_percent))
    assets = Decimal(str(inputs.earmarked_assets))
    budget = _number(inputs.monthly_investment_budget)
    pension = _number(inputs.annual_pension_today)
    inflation_factor = (ONE + inflation / HUNDRED) ** years
    annual_spending = spending * 12 * inflation_factor
    # Both spending and the declared pension start on today's purchasing-power
    # basis. Indexation describes pension increases AFTER retirement only.
    annual_pension = None if pension is None else pension * inflation_factor
    withdrawal_corpus = None if annual_pension is None else max(annual_spending - annual_pension, ZERO) / (withdrawal / HUNDRED)
    retirement_years = inputs.longevity_age - inputs.retirement_age
    # Cross-check in retirement-start purchasing power with a 0% real return.
    # Non-indexed pension loses real value; indexed pension retains real value.
    finite_real_zero = None if annual_pension is None else sum((max(annual_spending - annual_pension / ((ONE + inflation / HUNDRED) ** year if not inputs.pension_inflation_linked else ONE), ZERO) for year in range(retirement_years)), ZERO)
    target = None if withdrawal_corpus is None else max(withdrawal_corpus, finite_real_zero)
    fp = twin.get("financial_position") or {}
    income, expenses = monthly_field(fp, "income"), monthly_field(fp, "expenses")
    other = Decimal(str(inputs.other_goal_monthly_commitments))
    reserve = Decimal(str(inputs.reserve_monthly_commitment))
    raw_surplus = None if income is None or expenses is None else max(income - expenses, ZERO)
    capacity = None if raw_surplus is None else max(raw_surplus - other - reserve, ZERO)
    fire_budget = None if budget is None else max(budget - other - reserve, ZERO)
    contribution = None if fire_budget is None or capacity is None else min(fire_budget, capacity)
    # Round only the committed monthly transfer used by allocation and projection.
    contribution = None if contribution is None else Decimal(_money(contribution))
    missing = []
    if pension is None:
        missing.append("Annual pension income and indexation: enter zero explicitly if no pension is expected; no pension was inferred from occupation.")
    if budget is None:
        missing.append("Confirmed monthly investment willingness: positive surplus is not consent to invest it.")
    if capacity is None:
        missing.append("Recorded income, expenses and monthly/annual cashflow cadence are required to establish monthly capacity.")
    psych, cap, preference = _preferences(twin, years, expenses)
    if psych["status"] != "applied":
        missing.append("Complete psychometric risk willingness and loss sensitivity scores before selecting a personalised mix.")
    plans, recommended = _plans(preference, cap, contribution)
    citations = applied_principles(PRINCIPLES)
    if len(citations) != len(PRINCIPLES):
        missing.append("An exact FIRE skill section could not be verified; refresh sources before relying on this plan.")
        recommended = None
    projection = None if target is None else _projection(assets, target, contribution, rate, months)
    finite_projection = None if finite_real_zero is None else _projection(assets, finite_real_zero, contribution, rate, months)
    sensitivity = []
    if target is not None:
        for label, scenario_rate in (("lower", rate - 2), ("entered", rate), ("higher", rate + 2)):
            scenario = _projection(assets, target, contribution, scenario_rate, months)
            sensitivity.append({"label": label, "annual_return_percent": float(scenario_rate),
                                "required_monthly_contribution": _money(scenario["required"]),
                                "projected_corpus": _money(scenario["projected"]), "gap_at_retirement": _money(scenario["gap"])})
    fd_options, fd_missing = _fd_options(twin, recommended, today, inputs.current_age)
    missing.extend(fd_missing)
    status = "needs_inputs" if pension is None or budget is None or capacity is None else "preferences_required" if psych["status"] != "applied" else "source_verification_required" if len(citations) != len(PRINCIPLES) else "budget_exceeds_capacity" if budget > raw_surplus else "funding_gap" if projection and projection["gap"] > Decimal("0.01") else "scenario_on_track"
    facts = [{"label": label, "value": value, "path": path, "unit": unit, "source": source} for label, value, path, unit, source in (
        ("Current age", inputs.current_age, "planning_inputs.current_age", "years", "User-confirmed FIRE inputs"),
        ("Target retirement age", inputs.retirement_age, "planning_inputs.retirement_age", "years", "User-confirmed FIRE inputs"),
        ("Today's monthly retirement spending", _money(spending), "planning_inputs.monthly_spending_today", "INR/month", "User-confirmed FIRE inputs"),
        ("Assets earmarked only for FIRE", _money(assets), "planning_inputs.earmarked_assets", "INR", "User-confirmed FIRE inputs; twin assets are not added again"),
        ("Confirmed total saving/investment willingness", _money(budget), "planning_inputs.monthly_investment_budget", "INR/month", "User-confirmed total contribution ceiling before other-goal and reserve commitments, not inferred from surplus"),
        ("Monthly income", _money(income), "financial_position.income", "INR/month", "Recorded cadence-normalised twin cashflow"),
        ("Monthly expenses", _money(expenses), "financial_position.expenses", "INR/month", "Recorded cadence-normalised twin cashflow; EMI is not subtracted twice"),
    )]
    calculations = [{"id": "inflated_spending", "label": "Annual spending at retirement", "formula": "monthly spending today × 12 × (1 + inflation_percent / 100)^years", "operands": {"monthly_spending": str(spending), "inflation_percent": str(inflation), "years": str(years)}, "result": _money(annual_spending), "unit": "INR/year"}]
    if annual_pension is not None:
        calculations.append({"id": "pension_at_retirement", "label": "First-year pension on the same retirement-date basis", "formula": "annual pension in today's purchasing power × (1 + inflation_percent / 100)^years", "operands": {"annual_pension_today": str(pension), "inflation_percent": str(inflation), "years": str(years)}, "result": _money(annual_pension), "unit": "INR/year at retirement start"})
    if capacity is not None:
        calculations.append({"id": "capacity", "label": "Uncommitted monthly capacity", "formula": "max(income − expenses − other-goal commitments − reserve commitment, 0)", "operands": {"income": str(income), "expenses": str(expenses), "other_goals": str(other), "reserve": str(reserve)}, "result": _money(capacity), "unit": "INR/month"})
    if contribution is not None:
        calculations.append({"id": "contribution", "label": "Consent- and capacity-bounded FIRE contribution", "formula": "max(min(total confirmed willingness, max(income − expenses, 0)) − other-goal commitments − reserve commitment, 0)", "operands": {"total_willingness": str(budget), "raw_positive_surplus": str(raw_surplus), "other_goals": str(other), "reserve": str(reserve)}, "result": _money(contribution), "unit": "INR/month"})
    if target is not None and projection:
        calculations.extend([
            {"id": "withdrawal_corpus", "label": "Initial withdrawal-rate corpus comparison", "formula": "max(annual spending at retirement − annual pension at retirement, 0) / (withdrawal_rate_percent / 100)", "operands": {"annual_spending": str(annual_spending), "annual_pension": str(annual_pension), "withdrawal_rate_percent": str(withdrawal)}, "result": _money(withdrawal_corpus), "unit": "INR"},
            {"id": "corpus", "label": "Planning corpus: higher of the two explicit scenarios", "formula": "max(initial withdrawal-rate corpus, finite-horizon zero-real-return spending cross-check)", "operands": {"withdrawal_rate_corpus": str(withdrawal_corpus), "finite_horizon_real_zero_corpus": str(finite_real_zero)}, "result": _money(target), "unit": "INR at retirement start"},
            {"id": "contribution_required", "label": "Required end-of-month contribution in entered return scenario", "formula": "max(target − earmarked_assets × growth, 0) / annuity_factor; r_month=(1+r_annual/100)^(1/12)−1; growth=(1+r_month)^months; annuity_factor=(growth−1)/r_month, or months when rate=0", "operands": {"target": str(target), "earmarked_assets": str(assets), "annual_return_percent": str(rate), "months": str(months), "monthly_rate": str(projection["monthly_rate"]), "growth": str(projection["growth"]), "annuity_factor": str(projection["annuity_factor"])}, "result": _money(projection["required"]), "unit": "INR/month"},
        ])
        if contribution is not None:
            calculations.append({"id": "projected_corpus", "label": "Projected corpus with bounded contribution", "formula": "earmarked_assets × growth + monthly_contribution × annuity_factor", "operands": {"earmarked_assets": str(assets), "growth": str(projection["growth"]), "monthly_contribution": str(contribution), "annuity_factor": str(projection["annuity_factor"])}, "result": _money(projection["projected"]), "unit": "INR"})
    if finite_real_zero is not None and finite_projection is not None:
        calculations.extend([
            {"id": "longevity_crosscheck", "label": "Finite retirement spending cross-check at zero real return", "formula": "sum for year=0..retirement_years−1 of max(annual retirement-start spending − retirement-start pension / (1+inflation)^year, 0); indexed pension uses denominator 1", "operands": {"annual_retirement_start_spending": str(annual_spending), "annual_retirement_start_pension": str(annual_pension), "inflation_percent": str(inflation), "pension_indexed": str(inputs.pension_inflation_linked), "retirement_years": str(retirement_years), "real_return_percent": "0"}, "result": _money(finite_real_zero), "unit": "INR at retirement-start purchasing power"},
            {"id": "longevity_contribution_crosscheck", "label": "Monthly contribution for the finite-horizon cross-check", "formula": "max(finite-horizon zero-real-return corpus − earmarked_assets × growth, 0) / annuity_factor", "operands": {"finite_horizon_corpus": str(finite_real_zero), "earmarked_assets": str(assets), "growth": str(finite_projection["growth"]), "annuity_factor": str(finite_projection["annuity_factor"])}, "result": _money(finite_projection["required"]), "unit": "INR/month"},
        ])
    assumptions = [
        f"Inflation {inputs.inflation_percent}% a year, accumulation return {inputs.accumulation_return_percent}% a year and withdrawal rate {inputs.withdrawal_rate_percent}% are editable scenario assumptions, not forecasts or India safe-rate findings.",
        "Contributions arrive at each month-end. The entered effective annual return is converted to an equivalent monthly rate; no FD rate is compounded for the full retirement horizon.",
        "Annual pension is stated in today's purchasing power and is always inflated to the first retirement year, on the same basis as spending. After retirement, an indexed pension keeps that real value; an unindexed pension remains fixed in nominal rupees and loses real value in the finite-horizon cross-check. Pension tax and changes in real spending are not modelled.",
        "Entered earmarked assets are the entire opening FIRE balance. Portfolio, liquid reserves and FDs in the twin are not added again. Confirm that assets already assigned to other goals or emergency reserves are excluded.",
        "The planning corpus is the higher of the initial withdrawal-rate comparison and finite-horizon zero-real-return retirement spending check. This conservative application policy is not a source-prescribed safe rate or a guarantee, and still requires taxes, costs and contingencies review.",
        "Recorded expenses must include debt repayments. EMI is not deducted again. Other-goal and reserve monthly commitments are explicit additional earmarks; default zero requires user review, not evidence that none exist.",
        "Monthly investment willingness is the total saving/investment budget. Other-goal and reserve commitments consume that consent budget and the cashflow surplus once each; only the remainder is available to FIRE.",
        f"Longevity age {inputs.longevity_age} sets a {retirement_years}-year finite-spending cross-check at zero real retirement return. This cross-check is separate from the withdrawal-rate corpus, excludes death beyond that age, and does not simulate return sequences or establish lifelong adequacy.",
        "Current age is the age stated when the inputs were saved. Refresh it after each birthday; refreshing the as-of date does not automatically update age or pension facts.",
        "Return scenarios do not include separately computed tax, product fees, credit losses or lumpy healthcare needs. Establish their applicability before funding a product.",
    ]
    actions = []
    if missing:
        actions.append({"id": "confirm_fire_inputs", "label": "Confirm the missing FIRE inputs", "why": missing[0], "href": "/fire", "priority": "high"})
    if budget is not None and raw_surplus is not None and budget > raw_surplus:
        actions.append({"id": "reconcile_fire_budget", "label": "Reconcile willingness with available cashflow", "why": f"The declared total budget {_money(budget)} exceeds the monthly surplus {_money(raw_surplus)} before other-goal and reserve commitments; FIRE uses only the bounded remainder {_money(contribution)}.", "href": "/onboarding/finances", "priority": "high"})
    if budget is not None and raw_surplus is not None and other + reserve > min(budget, raw_surplus):
        actions.append({"id": "reconcile_existing_commitments", "label": "Reconcile existing goal and reserve commitments first", "why": f"Additional monthly earmarks {_money(other + reserve)} exceed the lower of total willingness and cashflow surplus {_money(min(budget, raw_surplus))}. They cannot all be funded under the entered budget; FIRE receives zero until priorities or capacity change.", "href": "/onboarding/goals", "priority": "high"})
    if projection and contribution is not None and projection["gap"] > Decimal("0.01"):
        path = (f"If willing, compare a total monthly budget of {_money(projection['required'] + other + reserve)}, including the additional other-goal and reserve earmarks; this is within recorded surplus but still needs explicit consent."
                if capacity is not None and projection["required"] <= capacity else
                f"Even fully allocating uncommitted capacity leaves an additional monthly capacity gap of {_money(max(projection['required'] - (capacity or ZERO), ZERO))}; compare lower spending, higher income or later retirement.")
        actions.append({"id": "close_fire_gap", "label": "Compare contribution, spending and retirement-date changes", "why": f"The entered scenario needs {_money(projection['required'])} per month versus {_money(contribution)} bounded contribution. {path} Do not raise risk to force a target.", "href": "/fire", "priority": "high"})
    if recommended is not None:
        amounts = recommended["monthly_amounts"]
        actions.append({"id": "review_fire_mix", "label": "Review the psychometric-matched monthly allocation", "why": f"Illustrative monthly amounts: diversified equity {_money(Decimal(amounts['equity']))}, FD set-aside {_money(Decimal(amounts['fd']))}, high-quality debt {_money(Decimal(amounts['high_quality_debt']))}. Product selection and suitability checks precede implementation.", "href": "/fire", "priority": "medium"})
        actions.append({"id": "review_fire_fd_terms", "label": "Compare FD tenors and bank exposure before booking", "why": "FD catalogue entries are alternative one-time deposit comparisons. Check residency, minimum booking amount, current quote, premature-access penalty, tax and aggregate same-bank exposure; future renewal rates are unknown.", "href": "/fd", "priority": "medium"})
    applied_controls = [row["rule"] for row in psych["implementation_controls"] if row["status"] == "applied"]
    if applied_controls:
        actions.append({"id": "write_fire_behavior_rules", "label": "Write the questionnaire-matched implementation rules", "why": " ".join(applied_controls), "href": "/fire", "priority": "medium"})
    actions.append({"id": "review_fire_policy", "label": "Review FIRE inputs annually and after a material change", "why": "Update spending, pension, earmarked assets, contribution consent and questionnaire preferences. Recheck plan assumptions rather than treating a deterministic path as a probability of success.", "href": "/fire", "priority": "medium"})
    return {"version": "fire-v1", "as_of": today.isoformat(), "status": status, "inputs": values,
            "summary": {"years_to_retirement": years, "months_to_retirement": months, "retirement_age": inputs.retirement_age,
                        "longevity_age": inputs.longevity_age, "annual_spending_at_retirement": _money(annual_spending),
                        "retirement_years": retirement_years, "finite_horizon_real_zero_corpus": _money(finite_real_zero),
                        "withdrawal_rate_corpus": _money(withdrawal_corpus),
                        "finite_horizon_required_monthly_contribution": _money(finite_projection["required"]) if finite_projection else None,
                        "annual_pension_at_retirement": _money(annual_pension), "target_corpus": _money(target),
                        "required_monthly_contribution": _money(projection["required"]) if projection else None,
                        "confirmed_monthly_budget": _money(budget), "fire_budget_after_commitments": _money(fire_budget), "monthly_capacity": _money(capacity), "monthly_contribution": _money(contribution),
                        "projected_corpus": _money(projection["projected"]) if projection else None,
                        "gap_at_retirement": _money(projection["gap"]) if projection else None,
                        "monthly_contribution_gap": _money(max(projection["required"] - contribution, ZERO)) if projection and contribution is not None else None},
            "facts": facts, "calculations": calculations, "assumptions": assumptions, "missing_information": missing,
            "psychometric_application": psych, "recommended_plan": recommended, "alternatives": plans,
            "sensitivity": sensitivity, "fd_options": fd_options, "principles": citations, "actions": actions,
            "limitations": ["This scenario is not a guarantee of financial independence or a safe withdrawal recommendation.",
                            "At age 65 the objective is financial independence; early retirement is relative to the user's own target, not assumed from the FIRE name.",
                            "No probability of success, retirement sequence simulation, execution order, bank eligibility, exact tax liability or future FD renewal rate is inferred."]}
