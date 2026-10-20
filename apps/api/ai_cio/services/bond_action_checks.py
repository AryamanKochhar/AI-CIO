"""Central guard for alternatives: one budget, no unsupported execution amounts."""
from decimal import Decimal, InvalidOperation


def _number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
        return number if number.is_finite() else None
    except (ValueError, TypeError, InvalidOperation):
        return None


def reconcile_bond_action_checks(payload: dict, policy: dict, constraints: dict | None = None) -> dict:
    constraints = constraints or {}
    ceiling = _number(policy.get("uncommitted_monthly_ceiling"))
    if ceiling is not None and ceiling < 0:
        ceiling = None
    assigned = _number(constraints.get("bond_allocation_budget"))
    if policy.get("earmarks_confirmed") is not True or assigned is None or assigned < 0 or ceiling is None or assigned > ceiling:
        assigned = None
    fixed, rate = _number(constraints.get("bond_fixed_cost")), _number(constraints.get("bond_cost_rate"))
    costs_known = fixed is not None and fixed >= 0 and rate is not None and rate >= 0
    withheld = []
    for group in ("catalogue_products", "eligible_products"):
        for product in payload.get(group) or []:
            if not isinstance(product, dict):
                continue
            units, cost = _number(product.get("units")), _number(product.get("estimated_cost"))
            supplied = any(product.get(key) is not None for key in ("units", "estimated_cost", "unit_budget"))
            valid = assigned is not None and units is not None and units > 0 and units == units.to_integral_value() and cost is not None and 0 < cost <= assigned
            lot = _number(product.get("lot_size"))
            price = _number(product.get("comparison_price"))
            valid = valid and lot is not None and lot >= 1 and lot == lot.to_integral_value() and units is not None and units % lot == 0
            valid = valid and price is not None and price > 0 and product.get("quote_status") == "verified_fresh_depth"
            valid = valid and (product.get("market_evidence") or {}).get("settlement_verified") is True
            expected = units * price * (1 + rate) + fixed if costs_known and units is not None and price is not None else None
            valid = valid and expected is not None and cost is not None and abs(expected - cost) <= Decimal("0.01")
            if supplied and not valid:
                withheld.append({"isin": product.get("isin"), "reason": "Quantity/cost is not supported by the assigned share of one confirmed budget, verified settlement/quote/lot and independently reconciled cash outlay including known costs."})
                for key in ("units", "estimated_cost", "unit_budget"):
                    product[key] = None
            elif supplied:
                product["unit_budget"] = f"{assigned:.2f}"
    return {
        "version": "bond-central-action-checks-v1", "passed": True,
        "monthly_ceiling": f"{ceiling:.2f}" if ceiling is not None else None,
        "bond_assigned_budget": f"{assigned:.2f}" if assigned is not None else None,
        "preferences": {"allow_gold": constraints.get("allow_gold") is True,
                        "fixed_cost": str(fixed) if fixed is not None and fixed >= 0 else None,
                        "cost_rate": str(rate) if rate is not None and rate >= 0 else None},
        "quantities_withheld": withheld, "execution_allowed": False,
        "comparison_basis": "pretax unless a separate supported transaction-specific tax calculation is supplied",
        "scope": "Products are alternatives within one shared budget, not additive allocations. Existing direct bonds and debt-fund units are not added again to portfolio or FIRE wealth. No orders are placed.",
    }
