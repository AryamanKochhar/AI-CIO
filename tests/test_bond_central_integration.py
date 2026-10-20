"""Sourced bond evidence reaches decisions without allocating a second budget."""
from copy import deepcopy
from datetime import date

import pytest

from ai_cio.services.agents.bond_agent import run_bond_agent
from ai_cio.services.agents.decision_suggestions import build_decision_suggestions
from ai_cio.services.bond_action_checks import reconcile_bond_action_checks
from ai_cio.services.orchestration.policy import validate_review_proof


class TermsOnly:
    def market_snapshot(self, products, *, as_of):
        return {"master": {}, "quotes": {}, "sources": [], "errors": [], "status": "empty"}


def bond_terms():
    return run_bond_agent({}, provider=TermsOnly(), as_of=date(2026, 10, 20))


def test_actual_sourced_terms_change_central_decision_with_exact_validated_skill_proof():
    result = build_decision_suggestions(twin={}, analysis_bits={
        "objective": "review_bond_portfolio", "bond_intelligence": bond_terms(),
    }, sector_opportunity={})
    row = result["items"][0]
    assert row["owner"] == "bond_agent" and row["id"] == "bond-sourced-terms"
    assert validate_review_proof(row)["passed"]
    assert {"bond_identity", "bond_cashflows", "bond_price_yield", "bond_suitability", "bond_gold", "bond_tax"} <= {p["id"] for p in row["proof"]["principles"]}
    assert len(row["proof"]["calculations"]) == 2
    assert all(c["unit"] == "years" for c in row["proof"]["calculations"])
    text = str(row["proof"])
    assert "IN0020220045" in text and "5091" in text
    assert "Fresh verified quote" in text
    assert row["calibrated_probability"] is False
    changed = deepcopy(row)
    changed["proof"]["facts"][0]["value"] = "Invented instrument"
    assert not validate_review_proof(changed)["passed"]


def test_terms_with_unresolved_sources_never_become_central_evidence():
    bonds = bond_terms()
    bonds["sources"] = []
    result = build_decision_suggestions(twin={}, analysis_bits={"bond_intelligence": bonds}, sector_opportunity={})
    assert not any(row["owner"] == "bond_agent" for row in result["items"])


@pytest.mark.parametrize("override,ceiling", [
    ({}, None), ({"units": 101}, "15000"), ({"lot_size": None}, "15000"),
    ({"quote_status": "price_only"}, "15000"), ({"estimated_cost": "15001"}, "15000"),
    ({"price": 0}, "15000"), ({"units": True}, "15000"),
    ({"estimated_cost": 1}, "15000"), ({"comparison_price": 100}, "15000"),
    ({"market_evidence": {"settlement_verified": False}}, "15000"),
])
def test_central_guard_withholds_unsupported_amounts(override, ceiling):
    product = {"isin": "IN002026Y105", "units": 100, "lot_size": 100,
               "price": 99, "comparison_price": 99, "estimated_cost": 9910, "unit_budget": 10000,
               "market_evidence": {"settlement_verified": True},
               "quote_status": "verified_fresh_depth", **override}
    if override.get("price") == 0:
        product["comparison_price"] = 0
    payload = {"catalogue_products": [product], "eligible_products": [deepcopy(product)]}
    checks = reconcile_bond_action_checks(payload, {"uncommitted_monthly_ceiling": ceiling, "earmarks_confirmed": True},
        {"bond_allocation_budget": 15000, "bond_fixed_cost": 10, "bond_cost_rate": 0})
    assert len(checks["quantities_withheld"]) == 2
    assert checks["execution_allowed"] is False
    assert all(p["units"] is p["estimated_cost"] is p["unit_budget"] is None
               for group in payload.values() for p in group)


def test_product_alternatives_use_one_ceiling_without_mutating_original_wealth():
    payload = {"catalogue_products": [{"isin": "IN002026Y105", "units": 100,
        "lot_size": 100, "price": 99, "comparison_price": 99, "estimated_cost": 9910, "unit_budget": 999999,
        "market_evidence": {"settlement_verified": True},
        "quote_status": "verified_fresh_depth"}], "holdings": [{"valuation": "1234"}]}
    checks = reconcile_bond_action_checks(payload, {"uncommitted_monthly_ceiling": "10000", "earmarks_confirmed": True},
        {"bond_allocation_budget": 10000, "bond_fixed_cost": 10, "bond_cost_rate": 0})
    assert checks["quantities_withheld"] == []
    assert payload["catalogue_products"][0]["unit_budget"] == "10000.00"
    assert payload["holdings"] == [{"valuation": "1234"}]
    assert "alternatives" in checks["scope"] and checks["execution_allowed"] is False


def test_shared_budget_alone_never_assigns_a_bond_purchase():
    payload = {"catalogue_products": [{"units": 100, "lot_size": 100,
        "comparison_price": 99, "estimated_cost": 9900, "quote_status": "verified_fresh_depth",
        "market_evidence": {"settlement_verified": True}}]}
    checks = reconcile_bond_action_checks(payload, {"uncommitted_monthly_ceiling": "10000", "earmarks_confirmed": True})
    assert checks["quantities_withheld"] and payload["catalogue_products"][0]["units"] is None


def test_bond_endpoint_has_real_terms_and_is_private_read_only(client, db):
    from ai_cio.services import identity
    user = identity.create_user(db, "Synthetic Bond endpoint fixture")
    db.commit()
    result = client.get(f"/users/{user.id}/bonds")
    assert result.status_code == 200, result.text
    assert result.headers["cache-control"] == "private, no-store"
    data = result.json()
    assert len(data["catalogue_products"]) == 3
    assert data["central_checks"]["execution_allowed"] is False
    assert all(p["price"] is p["units"] is None for p in data["catalogue_products"])
    assert client.get("/users/99999999/bonds").status_code == 404
