"""Resolve applied principles to real skill sections; never accept model citations."""
from __future__ import annotations

import hashlib
from pathlib import Path
import re

from ai_cio import settings
from ai_cio.services.finance_standards import source_context_for_skills

# Exact excerpts from the project's original condensed guides, not book quotations.
PRINCIPLES = {
    'mf_identity': ('mutual-fund-first-principles', 'Establish exact scheme identity', 'A scheme name alone does not establish its ISIN, Direct or Regular plan, Growth or IDCW option, benchmark or tax classification.'),
    'mf_benchmark': ('mutual-fund-first-principles', 'Compare matched total returns', 'Compare a fund and its appropriate total-return benchmark over the same dates and return basis.'),
    'mf_persistence': ('mutual-fund-first-principles', 'Review persistence before action', 'One weak return window does not establish persistent underperformance or justify a sale.'),
    'mf_overlap': ('mutual-fund-first-principles', 'Separate overlap from correlation', 'Weighted overlap is the sum of the smaller disclosed weights for each common security, without renormalizing partial disclosures.'),
    'mf_correlation': ('mutual-fund-first-principles', 'Separate overlap from correlation', 'Correlation needs aligned return observations and sufficient nonzero variance; it does not prove future diversification.'),
    'mf_costs': ('mutual-fund-first-principles', 'Compare costs within the same mandate', 'A lower TER does not by itself establish a suitable replacement fund.'),
    'mf_suitability': ('mutual-fund-first-principles', 'Use the Twin constraints', 'A fund review must consider the recorded horizon, liquidity, loss capacity and declared risk willingness together.'),
    'mf_data': ('mutual-fund-first-principles', 'Preserve unavailable evidence', 'Missing benchmark, holdings disclosure, tax classification or transactions means that dimension is not evaluated.'),
    'mf_tax_scope': ('tax-period-and-fund-classification', 'Withhold unsupported switch estimates', 'Do not apply a blanket short-term rule to every debt fund or assume every other mutual fund is equity-oriented.'),
    'portfolio_lookthrough': ('portfolio-first-principles', 'Count exposures once', 'Do not add fund-unit value again after looking through to its underlying holdings.'),
    'portfolio_reconcile': ('portfolio-first-principles', 'Reconcile specialist proposals', 'Specialists may work in parallel, but their proposals must use one shared cash budget and one final set of constraints.'),
    'portfolio_joint': ('portfolio-first-principles', 'Use joint outcomes and constraints', 'Diversification depends on weights and joint-return behavior, not the number of fund names.'),
    'equity_fundamentals': ('equity-analysis-first-principles', 'Separate price from value', 'A market price or technical indicator is not fundamental value.'),
    'equity_business': ('equity-analysis-first-principles', 'Explain business mechanisms', 'A single ratio or a one-day sector move cannot establish the investment case.'),
    'fd_contract': ('fd-comparison-first-principles', 'Compare the actual deposit contract', 'A card rate is not an after-tax yield, early-access promise or future renewal rate.'),
    'fd_not_fund': ('fd-comparison-first-principles', 'Distinguish deposits from fund units', 'A debt mutual fund is not a bank fixed deposit and does not receive deposit insurance merely because its holdings include debt.'),
    'tax_fund_identity': ('tax-period-and-fund-classification', 'Establish period and classification', 'Mutual fund tax classification requires verified scheme attributes and acquisition and disposal dates; a fund name or debt label is insufficient.'),
    'goal_return_basis': ('trajectory-first-principles', 'Tie assumptions to the spending plan', 'Historical fund performance is not a forecast input unless the user chooses an explicit scenario.'),

    'fire_spending': ('fire-planning', 'Define the spending liability', 'Financial independence is a funded spending plan, not a universal corpus multiple.'),
    'fire_withdrawal': ('fire-planning', 'Treat withdrawal rates as scenarios', 'A withdrawal-rate scenario is not a guaranteed Indian safe rate.'),
    'fire_contribution': ('fire-planning', 'Constrain contributions by consent and capacity', 'Use the lower of declared investment willingness and uncommitted surplus; never assume all surplus is available.'),
    'fire_risk': ('fire-planning', 'Respect willingness and loss capacity', "A funding gap does not justify increasing risk beyond the investor's stated willingness or financial capacity."),
    'fire_fd': ('fire-planning', 'Match deposit maturities to cash needs', "Today's fixed deposit rate applies only to an eligible deposit booked for its stated term, not to future renewals."),
    'fire_joint': ('fire-planning', 'Earmark assets and contributions once', "An emergency reserve or another goal's earmarked assets cannot also be counted toward FIRE."),
    'fire_review': ('fire-planning', 'Review outcomes without promising them', 'A deterministic projection does not measure sequence risk or a probability of success.'),
    "real_basis": ("purchasing-power-and-sequence", "Measure consumption rather than account digits", "Missing inflation leaves real outcomes unevaluated."),
    "sequence_order": ("purchasing-power-and-sequence", "Separate saving from spending down", "Matching average returns does not match withdrawal outcomes."),
    "investment_commitment": ("cost-and-cashflow-first-principles", "Separate capacity from commitment", "Available surplus is not consent to invest that amount."),
    "fee_mechanism": ("cost-and-cashflow-first-principles", "Follow the fee cashflow", "Costs reduce the capital left to compound."),
    "bond_cashflow": ("fixed-income-first-principles", "Start from promised cashflows", "Coupon rate is not yield to maturity or total return."),
    "price_evidence": ("market-evidence-and-uncertainty", "Identify what was measured", "A price indicator does not establish fundamental value."),
    "joint_risk": ("market-evidence-and-uncertainty", "Explain diversification through joint outcomes", "Portfolio risk requires both weights and joint-return evidence."),
    "capacity": ("nism-investment-adviser-l1", "Review financial capacity before asset selection", "A high psychometric risk score does not establish capacity for loss."),
    "shared_goals": ("nism-investment-adviser-l1", "Prioritise goals without counting assets twice", "The same cash cannot independently fund every goal; overlapping funding is a limitation unless the engine implements joint allocation."),
    "goal_options": ("nism-investment-adviser-l1", "Review options and next step", "State which inputs would change the assessment."),
    "tradeoff_matrix": ("nism-investment-adviser-l2", "Use a trade-off matrix", "Do not invent an amount to complete a row."),
    "liquidity": ("liquidity-and-deposit-safety", "Match access to actual commitments", "Coverage ratios require an identified denominator and cadence."),
    "reserve_policy": ("liquidity-and-deposit-safety", "Match access to actual commitments", "A reserve-month assumption is configurable planning policy, not a legal minimum."),
    "fd_access": ("liquidity-and-deposit-safety", "Compare deposits fairly", "A higher rate does not automatically improve fit."),
    "fd_insurance": ("liquidity-and-deposit-safety", "Insurance is conditional", "This is not a per-FD or per-branch allowance."),
    "retirement_basis": ("nism-retirement-adviser", "State the projection basis", "A nominal corpus is not purchasing power."),
    "retirement_income": ("nism-retirement-adviser", "Separate accumulation from withdrawals", "Occupation and household labels do not supply those facts."),
    "withdrawal_risk": ("nism-retirement-adviser", "Explain sequence risk accurately", "A constant-return accumulation path does not evaluate that risk."),
    "tax_basis": ("tax-source-discipline", "Establish applicability first", "A holding valuation alone cannot establish realized gains."),
    "tax_coverage": ("tax-source-discipline", "Use calculations only within coverage", "Missing dates or cost basis mean not evaluated for affected calculations, rather than zero tax."),
    "costs": ("common-sense-investing", "Compare like with like", "Unknown costs stay unknown."),
    "rebalancing": ("common-sense-investing", "Rebalancing is a policy review", "Consider reviewing future contributions before discussing a sale, and explain tax, transaction cost, liquidity and tracking trade-offs."),
    "exposure": ("common-sense-investing", "Diversification is exposure, not product count", "Report unclassified exposure explicitly; no universal holding count proves adequate diversification."),
    "market_gate": ("canslim-strict-mode", "Supported educational comparison", "A positive framework observation does not establish suitability or override tax/cost concerns."),
    "market_missing": ("canslim-strict-mode", "Unsupported case", "If fundamental, price or volume evidence is absent, report the relevant dimensions as not evaluated."),
    "behaviour": ("psychology-of-money", "Separate statement, observation and interpretation", "A questionnaire records declared preferences."),
    "policy_limits": ("investment-policy-and-risk", "Preserve evidence limits", "A service threshold is an application policy unless an identified source establishes otherwise."),
}


_PRINCIPLE_SOURCE_IDS = {'fire_spending': ['fire_sebi_retirement', 'fire_sebi_inflation', 'nism_retirement'], 'fire_withdrawal': ['fire_morningstar2025', 'nism_retirement'], 'fire_contribution': ['nism_retirement', 'cfa_suitability'], 'fire_risk': ['fire_cfa_risk', 'cfa_suitability'], 'fire_fd': ['fire_sbi_rates', 'fire_hdfc_rates', 'fire_icici_rates', 'dicgc_guide'], 'fire_joint': ['nism_retirement', 'fire_sebi_retirement'], 'fire_review': ['fire_morningstar2025', 'nism_retirement']}


_PRINCIPLE_SOURCE_IDS.update({'mf_identity': ['mf_nism_distributors', 'mf_amfi_disclosures'], 'mf_benchmark': ['mf_nism_distributors', 'mf_sebi_master_2026', 'cfa_performance'], 'mf_persistence': ['mf_nism_distributors', 'cfa_performance'], 'mf_overlap': ['mf_amfi_disclosures', 'mf_sebi_master_2026'], 'mf_correlation': ['cfa_performance', 'mf_nism_distributors'], 'mf_costs': ['sebi_fund_costs', 'mf_sebi_master_2026'], 'mf_suitability': ['mf_nism_distributors', 'cfa_suitability'], 'mf_data': ['mf_amfi_disclosures', 'cfa_performance'], 'mf_tax_scope': ['tax_act_2025_fa2026', 'tax_act_transition'], 'portfolio_lookthrough': ['cfa_portfolio_planning', 'cfa_covariance'], 'portfolio_reconcile': ['cfa_portfolio_planning', 'cfa_performance'], 'portfolio_joint': ['cfa_covariance', 'cfa_portfolio_planning'], 'equity_fundamentals': ['equity_cfa_valuation', 'equity_nse_filings'], 'equity_business': ['equity_cfa_financial', 'equity_nism_research'], 'fd_contract': ['fd_rbi_deposit_faq', 'fire_sbi_terms', 'fire_hdfc_terms', 'fire_icici_terms'], 'fd_not_fund': ['dicgc_guide', 'fd_rbi_deposit_faq'], 'tax_fund_identity': ['tax_act_2025_fa2026', 'tax_act_transition'], 'goal_return_basis': ['fire_morningstar2025', 'nism_retirement']})

def resolve_principle(principle_id: str) -> dict | None:
    spec = PRINCIPLES.get(principle_id)
    if spec is None:
        return None
    skill, section, excerpt = spec
    path = Path(settings.ROOT) / ".cursor" / "skills" / skill / "SKILL.md"
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        return None
    marker = f"## {section}"
    heading = text.find(marker)
    if heading < 0:
        return None
    end = text.find("\n## ", heading + len(marker))
    block = text[heading:end if end >= 0 else len(text)]
    offset = block.find(excerpt)
    if offset < 0:
        return None
    absolute = heading + offset
    title = re.search(r"^# (.+)$", text, re.MULTILINE)
    return {
        "id": principle_id, "skill": skill, "title": title.group(1) if title else skill,
        "section": section, "excerpt": excerpt,
        "path": f".cursor/skills/{skill}/SKILL.md",
        "line_start": text.count("\n", 0, absolute) + 1,
        "line_end": text.count("\n", 0, absolute + len(excerpt)) + 1,
        "skill_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "section_sha256": hashlib.sha256(block.encode()).hexdigest(),
        "integrity": "exact_section_excerpt_verified",
        "source_refs": [row for row in source_context_for_skills((skill,)) if principle_id not in _PRINCIPLE_SOURCE_IDS or row["id"] in _PRINCIPLE_SOURCE_IDS[principle_id]],
        "scope": "Project-authored condensed skill excerpt; not a quotation from a complete book or proof of a financial outcome.",
    }


def applied_principles(ids: list[str]) -> list[dict]:
    rows = [resolve_principle(identifier) for identifier in dict.fromkeys(ids)]
    return [row for row in rows if row is not None]
