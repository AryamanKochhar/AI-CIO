"""Canonical score units and honest financial-capacity coverage (no I/O)."""
from decimal import Decimal

import pytest

from ai_cio.services.orchestration.strategy_evaluation import (
    _concentration_note, _liquidity_fit, _risk_capacity, _risk_willingness, evaluate_strategies,
)
from domain.decision.contracts import DecisionObjective, InvestmentContext, InvestmentStrategy


@pytest.mark.parametrize("score,expected", [
    (0, "lower"), (0.65, "lower"), (35, "lower"), ("35.01", "moderate"),
    (50, "moderate"), (Decimal("64.99"), "moderate"), (65, "higher"), (100, "higher"),
])
def test_risk_willingness_uses_canonical_zero_to_one_hundred_units(score, expected):
    assert _risk_willingness({"status": "known", "scores": {"risk_score": score}}) == expected


@pytest.mark.parametrize("score", [None, True, False, "not-a-score", -1, 101, "NaN", float("inf"), "-Infinity"])
def test_invalid_or_out_of_range_willingness_is_unknown(score):
    assert _risk_willingness({"status": "known", "scores": {"risk_score": score}}) == "unknown"


def test_uncompleted_assessment_does_not_become_known_from_a_numeric_score():
    assert _risk_willingness({"status": "unknown", "scores": {"risk_score": 90}}) == "unknown"


@pytest.mark.parametrize("liquid", ["0", "1000000"])
def test_known_liquidity_never_implies_comfortable_capacity_with_unknown_liabilities(liquid):
    finances = {"liquid": {"known": True, "value": liquid}, "liabilities": {"known": False}}
    assert _risk_capacity(finances, {}) == "not_fully_assessed"


@pytest.mark.parametrize("amount", [None, True, "NaN", "Infinity", -1, ""])
def test_presence_flags_without_usable_amounts_do_not_establish_capacity(amount):
    assert _risk_capacity({"liquid": {"known": True, "value": amount}}, {}) == "unknown"


def test_known_zero_liability_differs_from_unknown_liability():
    assert _risk_capacity({"liabilities": {"known": True, "total_balance": "0", "items": []}}, {}) == "not_fully_assessed"
    assert _risk_capacity({"liabilities": {"known": False, "total_balance": "0"}}, {}) == "unknown"
    assert _risk_capacity({}, {"total_value": {"known": True, "value": "500000"}}) == "not_fully_assessed"


def test_all_amounts_present_still_do_not_prove_full_loss_capacity():
    finances = {key: {"known": True, "value": val} for key, val in [("income", "100000"), ("expenses", "50000"), ("liquid", "200000")]}
    finances["liabilities"] = {"known": True, "total_balance": "0"}
    assert _risk_capacity(finances, {"total_value": {"known": True, "value": "1000000"}}) == "not_fully_assessed"


@pytest.mark.parametrize("score,higher_conflict", [(50, False), (65, True)])
def test_horizon_conflict_uses_correct_willingness_units_without_inventing_capacity(score, higher_conflict):
    context = InvestmentContext(user_id=1, decision_id="units", objective=DecisionObjective.ALLOCATE_CAPITAL,
        twin={"behaviour": {"status": "known", "scores": {"risk_score": score}}, "goals": {"items": [{"horizon_years": 2}]}},
        market_context={}, knowledge_evidence=[], decision_parameters={}, completeness={})
    strategy = InvestmentStrategy(name="Review", allocation={"equity": Decimal("80"), "cash": Decimal("20")}, rationale=[], assumptions=[], expected_characteristics={}, risks=[])
    result = evaluate_strategies(context, [strategy])[0]
    assert result.suitability_indicators["risk_capacity"] == "unknown"
    assert bool(result.conflicts) is higher_conflict
    assert not any("financial capacity" in item for item in result.conflicts)


@pytest.mark.parametrize("cash_share,expected", [(Decimal("15"), "good"), (Decimal("14.99"), "tight")])
def test_cash_share_policy_boundary_is_not_a_claim_of_emergency_adequacy(cash_share, expected):
    strategy = InvestmentStrategy(name="Policy", allocation={"cash": cash_share, "equity": Decimal("100") - cash_share}, rationale=[], assumptions=[], expected_characteristics={}, risks=[])
    # Even a known zero cash balance does not change a candidate-share policy
    # into a measured emergency buffer. The explanation must name that limit.
    finances = {"liquid": {"known": True, "value": "0"}}
    assert _liquidity_fit(finances, strategy) == expected
    context = InvestmentContext(user_id=1, decision_id="policy", objective=DecisionObjective.ALLOCATE_CAPITAL, twin={"financial_position": finances}, market_context={}, knowledge_evidence=[], decision_parameters={}, completeness={})
    result = evaluate_strategies(context, [strategy])[0]
    explanation = " ".join(result.strengths + result.weaknesses)
    assert "15% review policy" in explanation
    assert "usable cash buffer" not in explanation
    assert "no essential-expense coverage" in result.factors["liquidity_basis"]


def test_unusable_liquidity_is_not_reported_as_an_emergency_shortfall():
    context = InvestmentContext(user_id=1, decision_id="missing", objective=DecisionObjective.ALLOCATE_CAPITAL, twin={"financial_position": {"liquid": {"known": True, "value": None}}}, market_context={}, knowledge_evidence=[], decision_parameters={}, completeness={})
    strategy = InvestmentStrategy(name="Unknown", allocation={"cash": Decimal("100")}, rationale=[], assumptions=[], expected_characteristics={}, risks=[])
    result = evaluate_strategies(context, [strategy])[0]
    assert result.suitability_indicators["liquidity_fit"] == "unknown"
    assert any("not assessed" in item for item in result.weaknesses)
    assert not any("limited cash for emergencies" in item for item in result.weaknesses)


def test_few_positions_do_not_prove_underlying_concentration():
    # Three funds could each be broadly diversified; count cannot settle this.
    note = _concentration_note({"holdings_count": 3})
    assert "look-through" in note
    assert "highly concentrated" not in note
    assert _concentration_note({"holdings_count": 0}) == ""
