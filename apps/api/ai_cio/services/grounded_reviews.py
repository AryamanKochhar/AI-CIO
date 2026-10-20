"""Inspectable review findings: recorded fact -> arithmetic -> applied skill.

These are conditional reviews, not proofs of future performance. An exact source
excerpt is mandatory; models cannot invent citations, thresholds or calculations.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import json
from typing import Any

from ai_cio.services.skill_principles import applied_principles
from ai_cio.services.cashflow_math import monthly_field

ZERO = Decimal(0)
HUNDRED = Decimal(100)
TOPIC_LABELS = {"liquidity":"Reserve funding", "debt":"Borrowing terms", "goals":"Shared goal budgets", "retirement":"Retirement assumptions", "fd":"Deposit terms", "tax":"Tax coverage", "costs":"Product costs", "market":"Market evidence", "concentration":"Allocation policy", "data":"Missing inputs"}


def number(value: Any) -> Decimal | None:
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        out = Decimal(str(value))
        return out if out.is_finite() else None
    except (InvalidOperation, ValueError, TypeError):
        return None


def rounded(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):.2f}"


def rupees(value: Decimal) -> str:
    raw = str(abs(value).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    chunks = [raw[-3:]]
    raw = raw[:-3]
    while raw:
        chunks.append(raw[-2:])
        raw = raw[:-2]
    return ("−" if value < 0 else "") + "₹" + ",".join(reversed(chunks))


def fact(label: str, value: Any, path: str, *, unit: str = "", source: str = "Recorded financial twin", as_of: str | None = None) -> dict:
    return {"label": label, "value": str(value) if value is not None else None, "path": path,
            "unit": unit, "source": source, "as_of": as_of,
            "status": "recorded" if value is not None else "not_recorded"}


def calculation(label: str, operation: str, operands: list[Decimal], *, unit: str, formula: str) -> dict:
    if not all(value.is_finite() for value in operands):
        raise ValueError("Non-finite derivation operand")
    if operation == "difference":
        value = operands[0] - operands[1]
    elif operation == "positive_gap":
        value = max(operands[0] - operands[1], ZERO)
    elif operation == "sum":
        value = sum(operands, ZERO)
    elif operation in {"ratio", "percent"}:
        if operands[1] <= 0:
            raise ValueError("A positive denominator is required")
        value = operands[0] / operands[1] * (HUNDRED if operation == "percent" else 1)
    else:
        raise ValueError("Unsupported derivation")
    return {"label": label, "operation": operation, "operands": [str(n) for n in operands],
            "formula": formula, "result": rounded(value), "unit": unit,
            "rounding": "Half-up to two decimal places; display rounding only"}


def _months(goal: dict) -> Decimal | None:
    years = number(goal.get("horizon_years"))
    if years is not None and 0 < years <= 120:
        return years * 12
    try:
        days = (date.fromisoformat(str(goal.get("target_date"))[:10]) - date.today()).days
        return Decimal(days) / Decimal("30.4375") if days > 0 else None
    except (TypeError, ValueError):
        return None


def _monthly(fp: dict, name: str) -> Decimal | None:
    return monthly_field(fp,name)


def build_grounded_reviews(twin: dict, analysis_bits: dict | None = None) -> dict:
    bits = analysis_bits or {}
    fp = twin.get("financial_position") or {}
    portfolio = twin.get("portfolio") or {}
    holdings = portfolio.get("holdings") or []
    goals = (twin.get("goals") or {}).get("items") or []
    source = (fp.get("income") or {}).get("source") or "Recorded financial twin"
    income, expenses = _monthly(fp, "income"), _monthly(fp, "expenses")
    liquid = number((fp.get("liquid") or {}).get("value"))
    surplus = income - expenses if income is not None and expenses is not None else None
    candidates, rejected = [], []

    def add(*, identifier, theme, owner, title, detail, priority, principles, facts, calculations,
            conclusion, action, href, missing=None, assumptions=None, alternatives=None):
        citations = applied_principles(principles)
        if len(citations) != len(set(principles)):
            rejected.append({"id": identifier, "reason": "An exact applied skill excerpt is unavailable"})
            return
        missing = list(missing or [])
        if theme == "goals":
            missing.append("Confirmed monthly investment budget; recorded surplus is not an agreed contribution")
        proof = {"kind": "evidence_gap" if not calculations else "deterministic_derivation",
            "facts": facts, "calculations": calculations, "principles": citations,
            "conclusion": conclusion, "missing_information": missing or [],
            "assumptions": assumptions or [], "alternatives": alternatives or [],
            "scope": "The arithmetic and cited premise support this conditional review; they do not prove suitability or an investment outcome."}
        proof["digest"] = hashlib.sha256(json.dumps(proof,sort_keys=True,default=str).encode()).hexdigest()
        candidates.append({"id": identifier, "theme": theme, "owner": owner, "title": title, "detail": detail,
            "topic_label": TOPIC_LABELS.get(theme,theme),
            "kind": theme, "source": "rules", "policy_priority": priority,
            "basis": "Recorded facts and reproducible derivation; exact skill-section citations below",
            "action": {"label": action, "href": href, "why": conclusion}, "proof": proof})

    cadence = fp.get("cashflow_cadence")
    cash_facts = [fact("Recorded cashflow cadence",cadence,"financial_position.cashflow_cadence",source=source),
        fact("Recorded income amount",(fp.get("income") or {}).get("value"),"financial_position.income",unit="INR",source=source),
        fact("Recorded expense amount",(fp.get("expenses") or {}).get("value"),"financial_position.expenses",unit="INR",source=source),
        fact("Monthly income used",rounded(income) if income is not None else None,"normalized.monthly_income",unit="INR/month",source="Recorded monthly cashflow" if cadence == "monthly" else "Annual cashflow divided by 12" if cadence == "annual" else "Cadence not established"),
        fact("Monthly expenses used",rounded(expenses) if expenses is not None else None,"normalized.monthly_expenses",unit="INR/month",source="Recorded monthly cashflow" if cadence == "monthly" else "Annual cashflow divided by 12" if cadence == "annual" else "Cadence not established")]
    cash_calcs = []
    if cadence == "annual":
        for name, amount in (("income",income),("expenses",expenses)):
            if amount is not None:
                cash_calcs.append(calculation(f"Normalize annual {name}","ratio",[number(fp[name]["value"]),Decimal(12)],unit="INR/month",formula=f"recorded annual {name} ÷ 12"))
    if (income is None or expenses is None) and ((fp.get("income") or {}).get("value") is not None or (fp.get("expenses") or {}).get("value") is not None):
        add(identifier="cashflow-inputs",theme="data",owner="cashflow_agent",title="Confirm cashflow amounts and cadence before budgeting",
            detail="A recorded balance or amount without a usable recurring cadence does not establish monthly contribution capacity.",priority=95,principles=["liquidity","capacity"],facts=cash_facts,calculations=[],
            conclusion="Confirm usable income, expenses and their cadence before relying on monthly coverage or contributions.",action="Check the recurring cashflows",href="/onboarding/finances",missing=["Usable recurring income and expenses", "Monthly or annual cashflow cadence"])
    # Cash earmarks are distinct from deposits and from an assumed essential budget.
    emergency = [g for g in goals if g.get("goal_type") == "emergency" and number(g.get("target_amount")) is not None]
    if emergency and liquid is not None and liquid >= 0:
        goal = min(emergency, key=lambda g: _months(g) or Decimal(9999))
        target, funded = number(goal.get("target_amount")), number(goal.get("current_funding"))
        if target is not None and funded is not None and target > 0 and funded >= 0:
            gap = max(target-funded,ZERO)
            months = _months(goal)
            calcs = [*cash_calcs,calculation("Recorded earmark gap", "positive_gap", [target,funded],unit="INR",formula="max(recorded target − recorded goal funding, 0)")]
            if expenses is not None and expenses > 0:
                calcs.append(calculation("Cash / recorded outgoings", "ratio", [liquid,expenses],unit="months",formula="liquid cash ÷ recorded monthly expenses"))
            priority = 45 if gap == 0 else 98 if months and months <= 12 and funded/target < Decimal("0.67") else 91 if months and months <= 12 else 68
            add(identifier="liquidity-earmark",theme="liquidity",owner="cashflow_agent",
                title=f"{goal.get('name') or 'Reserve'}: {rupees(gap)} still to earmark" if gap else "Verify access to the recorded reserve",
                detail=f"The recorded target is {rupees(target)} and its funding is {rupees(funded)}. Bank cash is {rupees(liquid)}; it is not automatically an additional earmark.",
                priority=priority,principles=["liquidity","shared_goals"],
                facts=[fact("Reserve target",target,f"goals.{goal.get('id')}.target_amount",unit="INR"),fact("Recorded reserve funding",funded,f"goals.{goal.get('id')}.current_funding",unit="INR"),fact("Liquid cash",liquid,"financial_position.liquid",unit="INR",source=(fp.get("liquid") or {}).get("source") or source),*cash_facts],
                calculations=calcs,conclusion="Confirm which existing assets actually back this reserve before committing the same cash to other goals.",
                action="Review the reserve earmark",href="/onboarding/goals",missing=["Essential versus discretionary expenses", "Whether goal funding already includes the recorded bank cash"],
                assumptions=["This is the user's recorded target, not a universal emergency-fund requirement.","Cash/outgoings is descriptive coverage, not proof that the reserve is adequate."],
                alternatives=["Ring-fence an existing verified liquid earmark", "Revise the recorded target or deadline after checking essential commitments"])

    # Debt review concerns obligations and missing borrowing terms, not stock weights.
    liab = fp.get("liabilities") or {}
    debts = liab.get("items") or []
    payments = [number(d.get("monthly_payment")) for d in debts]
    if debts and income is not None and income > 0 and all(p is not None and p >= 0 for p in payments):
        payment = sum(payments,ZERO)
        share = payment / income * HUNDRED
        add(identifier="debt-terms",theme="debt",owner="cashflow_agent",title=f"Loan payments use {rounded(share)}% of recorded income",
            detail=f"Recorded EMIs total {rupees(payment)}/month against {rupees(income)} income. Borrowing rates are not supplied, so repayment versus investing cannot be ranked yet.",
            priority=94 if share >= 15 else 74,principles=["capacity","policy_limits"],facts=[*cash_facts,fact("Recorded monthly loan payments",payment,"financial_position.liabilities.items[].monthly_payment",unit="INR/month")],
            calculations=[*cash_calcs,calculation("Debt-service share", "percent",[payment,income],unit="%",formula="sum(recorded monthly loan payments) ÷ monthly income × 100")],
            conclusion="Check APR, remaining term and prepayment terms before comparing debt repayment with new investing.",action="Check the borrowing terms",href="/onboarding/finances",
            missing=["Loan APR and remaining term", "Prepayment charges", "Whether expenses already include the EMI"],
            assumptions=["EMIs are not subtracted again from expenses.","The 15% review-priority branch is application triage policy, not a safe-debt or creditworthiness cutoff."],
            alternatives=["Compare a verified prepayment scenario", "Retain scheduled repayment if terms and liquidity justify it"])

    # One shared pool: do not assign the full surplus separately to each goal.
    requirements = []
    for goal in goals:
        target, funded, months = number(goal.get("target_amount")), number(goal.get("current_funding")), _months(goal)
        if target is not None and funded is not None and target >= 0 and funded >= 0 and months:
            requirements.append((goal,max(target-funded,ZERO),months,max(target-funded,ZERO)/months))
    near_retirement = [row for row in requirements if row[0].get("goal_type") == "retirement" and row[2] <= 120]
    if (goals and len(requirements) != len(goals)) or (not goals and holdings):
        add(identifier="goal-inputs",theme="goals",owner="goal_agent",title="Complete goal inputs before comparing funding plans",
            detail="An incomplete target, earmark or usable deadline prevents a supported shared contribution comparison.",priority=93,principles=["shared_goals","goal_options","investment_commitment"],
            facts=[fact("Recorded goals",len(goals),"goals.items",unit="goals"),fact("Goals with usable target, funding and horizon",len(requirements),"goals.items[complete]",unit="goals")],calculations=[],
            conclusion="Confirm the missing goal amounts, funding and dates; omitted values are not treated as zero.",action="Complete the goal assumptions",href="/onboarding/goals",missing=["A target, recorded current funding and usable remaining horizon for every compared goal"])
    if len(requirements) >= 2 and len(requirements) == len(goals) and surplus is not None and any(row[1] > 0 for row in requirements):
        combined = sum((row[3] for row in requirements),ZERO)
        calculations = [*cash_calcs,calculation("Recorded monthly surplus","difference",[income,expenses],unit="INR/month",formula="monthly income − monthly expenses")]
        facts = [*cash_facts]
        for goal,gap,months,need in requirements:
            facts.extend([fact(f"{goal.get('name')} target",goal["target_amount"],f"goals.{goal.get('id')}.target_amount",unit="INR"),fact("Earmarked funding",goal["current_funding"],f"goals.{goal.get('id')}.current_funding",unit="INR"),fact("Remaining horizon",months,f"goals.{goal.get('id')}.horizon",unit="months")])
            calculations.append(calculation(f"{goal.get('name')}: no-return monthly baseline","ratio",[gap,months],unit="INR/month",formula="max(target − earmarked funding, 0) ÷ remaining months; no return assumed"))
        calculations.append(calculation("Combined no-return monthly baseline","sum",[row[3] for row in requirements],unit="INR/month",formula="sum of each distinct goal's no-return monthly baseline"))
        add(identifier="joint-goal-budget",theme="goals",owner="goal_agent",
            title=f"{len(requirements)} goals share {rupees(surplus)} of monthly surplus",
            detail=f"Their combined no-return baseline is {rupees(combined)}/month. Giving the full {rupees(surplus)} separately to every goal would double-count the same contributions.",
            priority=88 if near_retirement else 98 if surplus > 0 and combined/surplus >= 3 else 92,
            principles=["shared_goals","goal_options","investment_commitment"],facts=facts,calculations=calculations,
            conclusion="Agree goal priorities and a single contribution budget; revisit target amounts or dates before assuming a higher return closes the gap.",action="Review shared goal priorities",href="/onboarding/goals",
            missing=["A joint allocation of contributions", "Whether current goal earmarks overlap", "Whether each target is nominal or inflation-adjusted"],
            assumptions=["Zero-return comparison only: not a minimum contribution, forecast or goal-success probability.","No tax, costs or inflation are included; horizon_years is treated as remaining years.","Any amount already funded is not counted as a new asset."],
            alternatives=["Change a discretionary target or deadline", "Compare affordable contribution changes using the scenario page"])

    for goal,gap,months,need in near_retirement[:1]:
        add(identifier="retirement-basis",theme="retirement",owner="retirement_agent",title=f"Retirement in {rounded(months/12)} years needs a spending-and-income plan",
            detail=f"The target less recorded funding is {rupees(gap)}. Spreading that gap over {rounded(months)} months gives a {rupees(need)}/month no-return baseline, not a required investment return.",
            priority=100 if months <= 60 else 85,principles=["retirement_basis","retirement_income","withdrawal_risk","real_basis","sequence_order"],
            facts=[fact("Retirement target",goal["target_amount"],f"goals.{goal.get('id')}.target_amount",unit="INR"),fact("Current retirement funding",goal["current_funding"],f"goals.{goal.get('id')}.current_funding",unit="INR"),fact("Remaining retirement horizon",months,f"goals.{goal.get('id')}.horizon",unit="months"),fact("Retirement spending and pension income",None,"retirement.spending_and_income")],
            calculations=[calculation("Retirement funding gap","positive_gap",[number(goal["target_amount"]),number(goal["current_funding"])],unit="INR",formula="max(target − recorded retirement funding, 0)"),calculation("No-return monthly baseline","ratio",[gap,months],unit="INR/month",formula="funding gap ÷ remaining months")],
            conclusion="Confirm retirement spending, pension income and inflation basis before interpreting the corpus target or a withdrawal plan.",action="Check the retirement assumptions",href="/onboarding/goals",
            missing=["Expected essential retirement spending", "Verified pension or other retirement income", "Inflation basis, longevity and healthcare assumptions", "A withdrawal-order stress test"],
            assumptions=["Occupation, age and household labels are not evidence of pension entitlement.","This accumulation comparison does not model sequence risk during withdrawals or prove a safe withdrawal rate."],
            alternatives=["Compare a later retirement date or a different spending target", "Run scenarios with verified contributions; keep withdrawal risk separate"])

    # FD terms and bank-level identity are different from monthly liquidity.
    deposits = (fp.get("fixed_deposits") or {}).get("items") or []
    valid_fds = [d for d in deposits if number(d.get("principal")) is not None and number(d["principal"]) > 0]
    if valid_fds:
        by_bank = {}
        for deposit in valid_fds:
            bank = str(deposit.get("bank_name") or "Bank identity missing").strip()
            by_bank[bank] = by_bank.get(bank,ZERO) + number(deposit["principal"])
        bank,total = max(by_bank.items(),key=lambda row:row[1])
        dated = [d for d in valid_fds if d.get("maturity_date")]
        dates = sorted({str(d["maturity_date"]) for d in dated})
        insurance_review = total > Decimal(500000)
        add(identifier="deposit-access",theme="fd",owner="fd_agent",
            title=f"Check bank-level eligibility for {rupees(total)} recorded at {bank}" if insurance_review else f"Check access terms for {len(valid_fds)} term deposit{'s' if len(valid_fds)>1 else ''}",
            detail=("The public insurance limit is conditional and aggregated by bank/right/capacity. These records do not establish the insured amount." if insurance_review else f"Recorded maturity dates: {', '.join(dates) if dates else 'not supplied'}. A booked rate does not tell us what is accessible early or after tax."),
            priority=96 if insurance_review else 64,principles=["fd_insurance","fd_access"],
            facts=[fact("Largest recorded bank FD principal",total,"financial_position.fixed_deposits.items grouped by bank_name",unit="INR"),fact("Recorded bank name",bank,"financial_position.fixed_deposits.items[].bank_name"),fact("Recorded maturity dates",", ".join(dates) or None,"financial_position.fixed_deposits.items[].maturity_date")],
            calculations=[calculation("Recorded principals at this bank","sum",[number(d["principal"]) for d in valid_fds if str(d.get("bank_name") or "Bank identity missing").strip()==bank],unit="INR",formula="sum(recorded FD principal with the same bank label); not all bank deposits")],
            conclusion="Verify the insured-bank identity, ownership/capacity, all same-bank balances and early-access terms; no covered/uncovered balance is calculated here.",action="Review deposit terms and ownership",href="/fd",
            missing=["Verified insured-bank identity", "Ownership/right/capacity", "Other same-bank deposits and accrued interest", "Premature withdrawal terms and personal tax context"],
            assumptions=["The ₹5,00,000 public reference includes eligible principal and interest; it is not per FD or per branch.","A recorded bank name alone does not establish eligibility. FD principal is not automatically immediately spendable cash."],
            alternatives=["Compare known maturity timing with committed cash needs", "Confirm access and coverage before considering any change of bank or term"])

    tax = (bits.get("specialist_checks") or {}).get("tax") or {}
    if tax.get("available"):
        missing_rows = tax.get("missing_data") or []
        missing_names = list(dict.fromkeys(str(r.get("security") or r.get("reason") or "unidentified record") for r in missing_rows if isinstance(r,dict)))
        summary = tax.get("summary") or {}
        realized = number(summary.get("realized_gains"))
        add(identifier="tax-coverage",theme="tax",owner="tax_agent",
            title=f"Resolve tax coverage for {len(missing_names)} incomplete position{'s' if len(missing_names)!=1 else ''}" if missing_names else "Keep realized gains separate from portfolio valuation",
            detail=(f"Missing acquisition records affect: {', '.join(missing_names[:3])}. An engine estimate is not a confirmed whole-portfolio liability." if missing_names else f"The engine reports {rupees(realized) if realized is not None else 'unavailable'} realized gains for its recorded period; that is different from unrealized price changes."),
            priority=79 if missing_names else 63,principles=["tax_basis","tax_coverage","tradeoff_matrix"],
            facts=[fact("Engine rule version",tax.get("rule_version"),"tax_intelligence.rule_version",source="Versioned tax engine"),fact("Engine financial period",tax.get("financial_year"),"tax_intelligence.financial_year",source="Versioned tax engine"),fact("Reported realized gains",realized,"tax_intelligence.summary.realized_gains",unit="INR",source="Versioned tax engine",as_of=tax.get("as_of")),fact("Incomplete records",len(missing_names),"tax_intelligence.missing_data",unit="positions",source="Versioned tax engine")],
            calculations=[],conclusion="Verify acquisition/disposal records and applicable rule-period coverage before using tax estimates in an action.",action="Inspect tax lots and coverage",href="/tax",
            missing=missing_names or ["Personal residency/regime and full portfolio coverage need confirmation"],assumptions=["No tax rate or saving is inferred from a skill, market valuation or model memory.","Missing inputs are not zero tax; current-year realized amounts do not price an unspecified future sale."],
            alternatives=["Complete the missing lot evidence", "Keep any prospective sale conditional on a lot-specific, applicable calculation"])

    non_equity = [h for h in holdings if h.get("asset_class") != "equity" and h.get("amc") != "EQUITY"]
    undisclosed = [h for h in non_equity if number(h.get("expense_ratio")) is None]
    if undisclosed:
        values = [number(h.get("valuation")) for h in undisclosed]
        known_values = [v for v in values if v is not None and v >= 0]
        add(identifier="cost-disclosures",theme="costs",owner="cost_agent",title=f"Get cost disclosures for {len(undisclosed)} fund/allocation record{'s' if len(undisclosed)>1 else ''}",
            detail=f"Known valuations total {rupees(sum(known_values,ZERO))} for these records; unvalued records are excluded. No cost saving or plan-switch benefit can be calculated without disclosed charges.",
            priority=57,principles=["costs","fee_mechanism"],facts=[fact("Records without disclosed expense ratios",len(undisclosed),"portfolio.holdings[].expense_ratio",unit="records"),fact("Affected recorded names",", ".join(h.get("scheme_name") or "Unidentified allocation" for h in undisclosed),"portfolio.holdings[].scheme_name")],
            calculations=[calculation("Recorded value with missing expense disclosure","sum",known_values,unit="INR",formula="sum of known valuations for records without a supplied expense ratio")],
            conclusion="Identify the actual product, plan and disclosed charges before comparing like-for-like costs.",action="Add product and cost disclosures",href="/onboarding/documents",missing=["Verified scheme/plan identity", "Expense ratio, exit load and transaction cost", "Tax consequences of any proposed switch"],
            assumptions=["Only known valuations are summed. Missing valuations or expense ratios are not zero."],alternatives=["Retain the existing position pending disclosure", "Compare equivalent exposures and horizons only after costs are known"])

    market = bits.get("holding_market_data") or {}
    rows = [r for r in market.get("holdings",[]) if number((r.get("indicators") or {}).get("return_20d")) is not None]
    if rows:
        row = max(rows,key=lambda r:abs(number(r["indicators"]["return_20d"])))
        ind = row["indicators"]
        add(identifier="market-evidence-gate",theme="market",owner="market_agent",title=f"{row['symbol']}: a {rounded(number(ind['return_20d']))}% price move is not an earnings case",
            detail=f"The Dhan observation covers 20 sessions ending {row['as_of']}. Comparable earnings and a verified valuation basis are not supplied by this price history.",
            priority=59,principles=["market_gate","market_missing","price_evidence"],facts=[fact("20-session price return",ind["return_20d"],"holding_market_data.holdings[].indicators.return_20d",unit="%",source="Dhan completed daily candles",as_of=row["as_of"]),fact("RSI14",ind.get("rsi_14"),"holding_market_data.holdings[].indicators.rsi_14",source="Deterministic Wilder RSI over Dhan candles",as_of=row["as_of"]),fact("Comparable earnings figures",None,"fundamentals.comparable_earnings")],
            calculations=[],conclusion="Inspect dated fundamentals and the recorded goal context before treating momentum as an investment thesis.",action="Inspect the dated market evidence",href="#decision-market",missing=["Comparable dated earnings", "Verified valuation inputs", "Independent corporate-action adjustment check"],
            assumptions=["The return and RSI are supplied deterministic observations, not new forecasts or buy/sell triggers.","Dividends are excluded; data dates must remain visible."],alternatives=["Keep the observation as watch-list context", "Wait for the missing fundamental evidence"])

    equities = [h for h in holdings if h.get("asset_class") == "equity" or h.get("amc") == "EQUITY"]
    valued = [(h,number(h.get("valuation"))) for h in equities]
    valued = [(h,v) for h,v in valued if v is not None and v >= 0]
    total_equity = sum((v for _,v in valued),ZERO)
    if total_equity > 0:
        holding,value = max(valued,key=lambda row:row[1])
        weight = value/total_equity*100
        if weight > 25:
            add(identifier="equity-exposure",theme="concentration",owner="portfolio_agent",title=f"{holding.get('scheme_name')}: {rounded(weight)}% of recorded direct equity",
                detail="One exposure review covers the position and its allocation context. It is not repeated as separate single-stock, sector and diversification action cards.",
                priority=72,principles=["exposure","rebalancing","policy_limits","joint_risk"],
                facts=[fact("Largest recorded direct-equity value",value,"portfolio.holdings[].valuation",unit="INR",as_of=holding.get("valuation_date")),fact("Total valued direct equity",total_equity,"portfolio.holdings[direct_equity].valuation",unit="INR"),fact("Unvalued direct-equity records",len(equities)-len(valued),"portfolio.holdings[direct_equity]",unit="records")],
                calculations=[calculation("Largest position share","percent",[value,total_equity],unit="%",formula="largest recorded direct-equity position ÷ total valued direct equity × 100")],
                conclusion="Compare the position with a recorded policy and cash/goal constraints; consider contribution routing as well as any sale.",action="Review the allocation policy",href="/onboarding/twin",
                missing=["User-approved target allocation", "Look-through of pooled funds and unvalued assets", "Costs and lot-specific tax effects of a change"],
                assumptions=["25% is an application screening rule, not a sourced universal maximum.","The denominator is valued direct equity, not total wealth or the entire look-through portfolio."],
                alternatives=["Review future contribution routing", "Compare a conditional sale only with its actual costs and tax effects"])

    if not candidates:
        add(identifier="establish-inputs",theme="data",owner="cashflow_agent",title="Establish the inputs before comparing actions",
            detail="Known income, outgoings, cadence, goal deadlines and holdings are needed for an inspectable comparison.",priority=80,principles=["capacity","goal_options"],facts=cash_facts,calculations=[],
            conclusion="Confirm the missing financial fields; no allocation or financial capacity has been inferred.",action="Complete the recorded finances",href="/onboarding/finances",missing=["Usable income and expenses with cadence", "Goal amounts, earmarks and deadlines", "Holdings and account access terms"])

    # One causal theme per card. No artificial eight-card minimum or synonym fill.
    chosen = {}
    for row in candidates:
        if row["theme"] not in chosen or row["policy_priority"] > chosen[row["theme"]]["policy_priority"]:
            chosen[row["theme"]] = row
    selected = sorted(chosen.values(),key=lambda row:(-row["policy_priority"],row["id"]))[:8]
    summary = f"First review: {selected[0]['title'].rstrip('.')}." if selected else "Applied skill evidence is unavailable; no supported review is published."
    if len(selected) > 1:
        summary += " Next: " + ", ".join(row["topic_label"].lower() for row in selected[1:3]) + "."
    return {"items": selected,"summary":summary,"coverage":{"themes":[row["theme"] for row in selected],"candidate_count":len(candidates),"selected_count":len(selected),"rejected":rejected,"policy":"One card per causal theme, maximum eight; priority is explicit application triage, not a financial outcome model."}}
