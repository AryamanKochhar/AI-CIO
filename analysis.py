from collections import defaultdict
from decimal import Decimal

ZERO = Decimal("0")
def total_value(holdings): return sum((h["valuation"] for h in holdings), ZERO)
def allocation(holdings, key):
    total = total_value(holdings); buckets = defaultdict(lambda: ZERO)
    for h in holdings: buckets[h[key]] += h["valuation"]
    return [{key: name, "value": value, "percentage": (value / total * 100 if total else ZERO)} for name, value in sorted(buckets.items(), key=lambda x:x[1], reverse=True)]
def top_holdings(holdings, limit=5):
    total = total_value(holdings)
    return [{**h, "percentage": (h["valuation"] / total * 100 if total else ZERO)} for h in sorted(holdings, key=lambda h:h["valuation"], reverse=True)[:limit]]
def concentration_metrics(holdings):
    ranked = top_holdings(holdings, len(holdings)); amcs = allocation(holdings, "amc")
    return {"largest_holding_percentage": ranked[0]["percentage"] if ranked else ZERO, "top_3_percentage": sum((x["percentage"] for x in ranked[:3]), ZERO), "top_5_percentage": sum((x["percentage"] for x in ranked[:5]), ZERO), "largest_amc_percentage": amcs[0]["percentage"] if amcs else ZERO}
def sip_summary(transactions):
    successful = [t for t in transactions if t["transaction_type"] == "SIP_PURCHASE"]
    failed = [t for t in transactions if t["transaction_type"] == "FAILED_PAYMENT"]
    return {"successful_count": len(successful), "successful_amount": sum((t["amount"] or ZERO for t in successful), ZERO), "failed_count": len(failed), "failed": failed}

def validate_valuation(holding, tolerance=Decimal("1.00")):
    """Compare reported valuation to closing units × NAV without changing CAS values."""
    if not all(holding.get(k) is not None for k in ("closing_units", "nav", "valuation")):
        return {"status": "not confidently parsed"}
    calculated = holding["closing_units"] * holding["nav"]
    difference = holding["valuation"] - calculated
    return {"status": "ok" if abs(difference) <= tolerance else "discrepancy", "calculated_value": calculated, "reported_value": holding["valuation"], "difference": difference}

def reconcile_units(opening_units, transactions, closing_units, tolerance=Decimal("0.0001")):
    """Reconcile parsed unit movement. Failed/non-financial events never alter units."""
    if opening_units is None or closing_units is None:
        return {"status": "not confidently parsed"}
    movement = sum((t.get("units") or ZERO for t in transactions if t.get("transaction_type") in {"PURCHASE", "SIP_PURCHASE", "REDEMPTION"}), ZERO)
    expected = opening_units + movement
    return {"status": "ok" if abs(expected - closing_units) <= tolerance else "discrepancy", "expected_closing_units": expected, "reported_closing_units": closing_units, "difference": closing_units - expected}
