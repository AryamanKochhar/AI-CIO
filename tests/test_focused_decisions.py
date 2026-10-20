"""Keep measured actions concise while retaining source gaps for inspection."""
from decimal import Decimal

from ai_cio.services.agents.decision_suggestions import build_decision_suggestions, focus_reviews
from ai_cio.services.orchestration.policy import validate_review_proof


def test_measured_account_has_four_distinct_priorities_and_preserves_deferred_proofs():
    twin = {
        "financial_position": {"income": {"value": "100000"}, "expenses": {"value": "50000"},
                               "liquid": {"value": "25000"}, "cashflow_cadence": "monthly",
                               "fixed_deposits": {"items": [{"bank_name": "Synthetic Bank", "principal": "600000", "maturity_date": "2027-10-01"}]},
                               "liabilities": {"items": [{"monthly_payment": "20000"}]}},
        "portfolio": {"holdings": [
            {"scheme_name": "Synthetic equity", "amc": "EQUITY", "asset_class": "equity", "valuation": "100000"},
            {"scheme_name": "Synthetic pooled fund", "asset_class": "mutual_fund", "valuation": "10000"}]},
        "goals": {"items": [
            {"id": 1, "goal_type": "emergency", "name": "Reserve", "target_amount": "300000", "current_funding": "25000", "horizon_years": 1},
            {"id": 2, "goal_type": "retirement", "name": "Retirement", "target_amount": "10000000", "current_funding": "100000", "horizon_years": 4}]}}
    result = build_decision_suggestions(twin=twin, analysis_bits={}, sector_opportunity={})
    primary = result["items"]
    assert len(primary) == 4
    assert len({row["theme"] for row in primary}) == 4
    assert all(validate_review_proof(row)["passed"] for row in primary)
    assert sum(Decimal(str(row["relative_support_percent"])) for row in primary) == 100
    deferred = result["coverage"]["deferred_reviews"]
    assert any(row["id"] == "cost-disclosures" for row in deferred)
    assert all(row["proof"]["principles"] for row in deferred)
    assert "cost-disclosures" not in {row["id"] for row in primary}
    assert result["coverage"]["selected_count"] == 4


def test_fund_objective_retains_a_relevant_measured_fund_check_without_inventing_priority():
    candidates = [{"id": str(i), "theme": "goals", "policy_priority": 100-i} for i in range(4)]
    fund = {"id": "fund-overlap", "theme": "mf_overlap", "policy_priority": 70}
    selected, deferred = focus_reviews(candidates+[fund], objective="review_mutual_fund_portfolio")
    assert len(selected) == 4 and fund in selected
    assert fund["policy_priority"] == 70
    assert candidates[-1] in deferred


def test_completely_empty_account_gets_one_honest_input_task_and_no_fabricated_calculations():
    result = build_decision_suggestions(twin={}, analysis_bits={}, sector_opportunity={})
    assert len(result["items"]) == 1
    row = result["items"][0]
    assert row["id"] == "establish-inputs"
    assert row["proof"]["calculations"] == []
    assert row["proof"]["missing_information"]
