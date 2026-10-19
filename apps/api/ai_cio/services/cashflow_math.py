"""Pure cadence normalization; stock balances are never treated as cashflows."""
from decimal import Decimal, InvalidOperation


def monthly_amount(value, cadence: str | None, *, legacy_monthly: bool = False) -> Decimal | None:
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    if not amount.is_finite() or amount < 0:
        return None
    if cadence == "annual":
        return amount / 12
    if cadence == "monthly" or (cadence is None and legacy_monthly):
        return amount
    return None


def monthly_field(position: dict, name: str, *, legacy_monthly: bool = False) -> Decimal | None:
    node = position.get(name)
    if isinstance(node, dict):
        if node.get("known") is False:
            return None
        cadence = position.get("cashflow_cadence") or node.get("cadence")
        value = node.get("value")
    else:
        cadence, value = position.get("cashflow_cadence"), node
    return monthly_amount(value, cadence, legacy_monthly=legacy_monthly)
