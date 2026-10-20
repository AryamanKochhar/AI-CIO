"""Independent arithmetic, consent boundaries and preference integration tests."""
from copy import deepcopy
from decimal import Decimal
import json
import math

import pytest
from pydantic import ValidationError

from ai_cio.api.schemas import FirePlanningInputs
from ai_cio.services.fire_planner import build_fire_plan


def inputs(**changes):
    return {"current_age": 35, "retirement_age": 65, "monthly_spending_today": 40000,
            "monthly_investment_budget": 80000, "annual_pension_today": 0,
            "earmarked_assets": 1000000, "longevity_age": 95, **changes}


def twin(**scores):
    return {"behaviour": {"status": "known", "source": "psychometric_assessment",
                          "provenance": {"session_id": 5, "instrument_version": "1.0"},
                          "scores": {"risk_score": 80, "loss_aversion_score": 80,
                                     "decision_stability_score": 80, "anchoring_score": 80,
                                     "recency_bias_score": 80, "herding_score": 80,
                                     "overconfidence_score": 80, **scores}},
            "financial_position": {"cashflow_cadence": "monthly",
                                   "income": {"value": "200000", "known": True},
                                   "expenses": {"value": "50000", "known": True},
                                   "liquid": {"value": "1000000", "known": True},
                                   "fixed_deposits": {"items": [], "known": False},
                                   "liabilities": {"monthly_payments": "20000"}},
            "portfolio": {"total_value": {"value": "1000000000"}}}


def plan(data=None, profile=None, **kwargs):
    return build_fire_plan(profile or twin(), data or inputs(), as_of="2026-10-20", **kwargs)


def test_zero_return_oracle_and_longevity_target():
    result = plan(inputs(current_age=60, monthly_spending_today=1000, monthly_investment_budget=3000,
                         earmarked_assets=0, inflation_percent=0, accumulation_return_percent=0,
                         withdrawal_rate_percent=4))
    summary = result["summary"]
    assert summary["withdrawal_rate_corpus"] == "300000.00"  # 12000 / .04
    assert summary["finite_horizon_real_zero_corpus"] == "360000.00"  # 12000 * 30
    assert summary["target_corpus"] == "360000.00"
    assert summary["required_monthly_contribution"] == "6000.00"  # 360000 / 60
    assert summary["projected_corpus"] == "180000.00"
    assert summary["gap_at_retirement"] == "180000.00"


def test_compounding_matches_independent_effective_monthly_oracle():
    result = plan()
    summary = result["summary"]
    months = 30 * 12
    monthly_rate = math.pow(1.08, 1 / 12) - 1
    annuity = (math.pow(1 + monthly_rate, months) - 1) / monthly_rate
    target = max(40000 * 12 * math.pow(1.06, 30) / .035, 40000 * 12 * math.pow(1.06, 30) * 30)
    required = (target - 1000000 * math.pow(1.08, 30)) / annuity
    projected = 1000000 * math.pow(1.08, 30) + 80000 * annuity
    assert float(summary["target_corpus"]) == pytest.approx(target, abs=.01)
    assert float(summary["required_monthly_contribution"]) == pytest.approx(required, abs=.01)
    assert float(summary["projected_corpus"]) == pytest.approx(projected, abs=.01)


def test_risk_willingness_materially_changes_rank_and_rupee_allocations():
    low, high = plan(profile=twin(risk_score=10)), plan(profile=twin(risk_score=90))
    assert low["summary"] == high["summary"]  # No invented return uplift.
    assert low["recommended_plan"]["id"] == "preservation"
    assert high["recommended_plan"]["id"] == "growth"
    assert low["recommended_plan"]["monthly_amounts"]["equity"] == "0.00"
    assert high["recommended_plan"]["monthly_amounts"]["equity"] == "56000.00"
    assert low["alternatives"][0]["id"] != high["alternatives"][0]["id"]


def test_loss_aversion_polarity_is_not_reversed():
    sensitive = plan(profile=twin(risk_score=90, loss_aversion_score=10))
    adaptive = plan(profile=twin(risk_score=90, loss_aversion_score=90))
    assert sensitive["recommended_plan"]["equity_percent"] == 0
    assert adaptive["recommended_plan"]["equity_percent"] == 70
    assert "more adaptive" in adaptive["psychometric_application"]["polarity"]["loss_aversion"]["higher_means"]


def test_stability_and_other_bias_scores_produce_implementation_controls():
    calm = plan()
    uncertain = plan(profile=twin(decision_stability_score=10, recency_bias_score=10))
    assert uncertain["recommended_plan"]["id"] == "stability"
    assert not any(a["id"] == "write_fire_behavior_rules" for a in calm["actions"])
    action = next(a for a in uncertain["actions"] if a["id"] == "write_fire_behavior_rules")
    assert "quarterly" in action["why"]
    assert len(uncertain["psychometric_application"]["scores"]) == 7


def test_horizon_and_liquidity_capacity_override_high_declared_risk():
    near = plan(inputs(current_age=62))
    assert near["recommended_plan"]["equity_percent"] == 20
    low_liquid = twin()
    low_liquid["financial_position"]["liquid"]["value"] = "1"
    assert plan(profile=low_liquid)["recommended_plan"]["equity_percent"] == 20


def test_total_willingness_earmarks_and_capacity_are_not_counted_twice():
    result = plan(inputs(monthly_investment_budget=15000, other_goal_monthly_commitments=10000,
                         reserve_monthly_commitment=2000))
    summary = result["summary"]
    assert summary["monthly_capacity"] == "138000.00"  # EMI already in expenses.
    assert summary["fire_budget_after_commitments"] == "3000.00"
    assert summary["monthly_contribution"] == "3000.00"
    assert sum(Decimal(n) for n in result["recommended_plan"]["monthly_amounts"].values()) == Decimal(3000)
    assert plan(inputs(monthly_investment_budget=1000, other_goal_monthly_commitments=10000))["summary"]["monthly_contribution"] == "0.00"


def test_over_budget_is_flagged_and_transfer_never_exceeds_capacity():
    result = plan(inputs(monthly_investment_budget=200000, other_goal_monthly_commitments=10000))
    assert result["status"] == "budget_exceeds_capacity"
    assert result["summary"]["monthly_contribution"] == "140000.00"
    assert next(a for a in result["actions"] if a["id"] == "reconcile_fire_budget")["href"] == "/onboarding/finances"


def test_missing_willingness_never_invests_the_surplus():
    result = plan(inputs(monthly_investment_budget=None))
    assert result["status"] == "needs_inputs"
    assert result["summary"]["monthly_contribution"] is None
    assert result["summary"]["projected_corpus"] is None
    assert result["recommended_plan"] is None
    assert all(all(v is None for v in p["monthly_amounts"].values()) for p in result["alternatives"])


def test_unknown_cadence_and_unrecorded_pension_stay_unknown():
    profile = twin()
    profile["financial_position"]["cashflow_cadence"] = "irregular"
    result = plan(inputs(annual_pension_today=None), profile)
    assert result["summary"]["monthly_capacity"] is None
    assert result["summary"]["target_corpus"] is None
    assert result["summary"]["required_monthly_contribution"] is None
    assert result["recommended_plan"] is None


def test_missing_preferences_withholds_personalised_plan():
    profile = twin()
    profile["behaviour"] = {"status": "unknown"}
    result = plan(profile=profile)
    assert result["status"] == "preferences_required"
    assert result["recommended_plan"] is None
    assert result["psychometric_application"]["effective_risk_score"] is None
    assert result["summary"]["target_corpus"] is not None


def test_earmarked_assets_are_the_only_opening_balance():
    profile = twin()
    before = plan(profile=profile)["summary"]
    profile["portfolio"]["total_value"]["value"] = "999999999999"
    profile["financial_position"]["liquid"]["value"] = "999999999999"
    assert plan(profile=profile)["summary"] == before


def test_annual_cashflow_is_normalised_once():
    profile = twin()
    profile["financial_position"]["cashflow_cadence"] = "annual"
    profile["financial_position"]["income"]["value"] = "2400000"
    profile["financial_position"]["expenses"]["value"] = "600000"
    assert plan(profile=profile)["summary"] == plan()["summary"]


def test_pension_indexation_and_longevity_change_real_spending_requirement():
    fixed = plan(inputs(annual_pension_today=100000))
    indexed = plan(inputs(annual_pension_today=100000, pension_inflation_linked=True))
    assert fixed["summary"]["annual_pension_at_retirement"] == indexed["summary"]["annual_pension_at_retirement"]
    assert float(fixed["summary"]["annual_pension_at_retirement"]) == pytest.approx(100000 * math.pow(1.06, 30), abs=.01)
    assert float(fixed["summary"]["target_corpus"]) > float(indexed["summary"]["target_corpus"])
    short = plan(inputs(longevity_age=85))
    long = plan(inputs(longevity_age=105))
    assert float(long["summary"]["finite_horizon_real_zero_corpus"]) > float(short["summary"]["finite_horizon_real_zero_corpus"])
    assert float(long["summary"]["target_corpus"]) > float(short["summary"]["target_corpus"])


def test_sensitivity_is_monotonic_and_not_a_success_probability():
    result = plan()
    low, entered, high = result["sensitivity"]
    assert float(low["required_monthly_contribution"]) > float(entered["required_monthly_contribution"]) > float(high["required_monthly_contribution"])
    assert not any("probability" in row for row in result["sensitivity"])
    assert "probability" in " ".join(result["actions"][-1].values())


def test_cents_are_preserved_in_every_allocation():
    result = plan(inputs(monthly_investment_budget=12345.67))
    for candidate in result["alternatives"]:
        assert sum(Decimal(x) for x in candidate["monthly_amounts"].values()) == Decimal("12345.67")
        assert sum(candidate[k] for k in ("equity_percent", "fd_percent", "high_quality_debt_percent")) == 100


def test_current_fd_quotes_are_dated_alternatives_not_recurring_contracts():
    result = plan()
    assert len(result["fd_options"]) == 9
    for row in result["fd_options"]:
        assert row["quote_status"] == "current_snapshot"
        assert row["comparison_rate_percent"] > 0
        assert row["monthly_allocation"] == result["recommended_plan"]["monthly_amounts"]["fd"]
        assert "not additive" in row["allocation_basis"]
        assert "one-time" in row["allocation_basis"]
        assert row["existing_bank_principal"] is None
        assert "unknown future rates" in row["rate_application"]


@pytest.mark.parametrize("catalog", [[], {"products": "invalid"}, {"products": [{"annual_rate_percent": "NaN", "min_amount": 1000, "tenor_months": 12}]}])
def test_malformed_catalogue_never_invents_a_product_or_rate(monkeypatch, catalog):
    class FakePath:
        def __init__(self, *args):
            pass

        def __truediv__(self, other):
            return self

        def read_text(self, **kwargs):
            return json.dumps(catalog)

    monkeypatch.setattr("ai_cio.services.fire_planner.Path", FakePath)
    result = plan()
    assert result["fd_options"] == []
    assert any("FD" in text for text in result["missing_information"])


def test_stale_and_future_fd_quotes_cannot_be_current_recommendations():
    for at in ("2026-10-19", "2026-10-28"):
        result = build_fire_plan(twin(), inputs(), as_of=at)
        assert all(row["comparison_rate_percent"] is None and row["monthly_allocation"] is None for row in result["fd_options"])


def test_same_bank_exposure_and_senior_eligibility_are_conditional():
    profile = twin()
    profile["financial_position"]["fixed_deposits"] = {"known": True, "items": [{"bank_name": "State Bank of India", "principal": "600000"}]}
    result = plan(inputs(current_age=61), profile)
    sbi = next(r for r in result["fd_options"] if r["id"] == "sbi-callable-12m")
    assert sbi["review_status"] == "review_existing_bank_exposure_before_adding"
    assert sbi["senior_age_met"] is True
    assert sbi["comparison_rate_percent"] == sbi["annual_rate_percent"]  # No inferred senior eligibility.
    assert "same right" in sbi["insurance_review"]
    assert "insured_amount" not in sbi


def test_every_principle_is_an_exact_real_section_and_failure_is_closed(monkeypatch):
    result = plan()
    assert len(result["principles"]) == 7
    assert all(p["integrity"] == "exact_section_excerpt_verified" for p in result["principles"])
    monkeypatch.setattr("ai_cio.services.fire_planner.applied_principles", lambda ids: [])
    result = plan()
    assert result["status"] == "source_verification_required"
    assert result["recommended_plan"] is None


@pytest.mark.parametrize("field,value", [("current_age", True), ("current_age", 35.5), ("retirement_age", 35),
    ("longevity_age", 65), ("monthly_spending_today", -1), ("monthly_investment_budget", True),
    ("annual_pension_today", float("inf")), ("inflation_percent", float("nan")),
    ("withdrawal_rate_percent", 0), ("earmarked_assets", float("nan")), ("pension_inflation_linked", "yes")])
def test_invalid_and_nonfinite_inputs_rejected(field, value):
    with pytest.raises(ValidationError):
        FirePlanningInputs.model_validate(inputs(**{field: value}))


def test_output_is_finite_json_and_input_objects_unchanged():
    data, profile = inputs(), twin()
    original = deepcopy((data, profile))
    json.dumps(plan(data, profile), allow_nan=False)
    assert (data, profile) == original
