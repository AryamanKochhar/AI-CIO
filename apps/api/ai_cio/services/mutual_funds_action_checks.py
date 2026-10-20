"""Cross-specialist MF action feasibility, without inventing tax or sale scope.

The existing tax summary describes realized activity and has simplified MF
classification. It must never be repurposed as a prospective switch quote.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import json
from typing import Any
from zoneinfo import ZoneInfo

from ai_cio.settings import ROOT


def _number(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = Decimal(str(value))
        return parsed if parsed.is_finite() else None
    except (InvalidOperation, TypeError, ValueError):
        return None


def _date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None


def _deposit_context(as_of: date) -> dict:
    try:
        catalogue = json.loads((ROOT / "knowledge" / "fd_rate_catalog.json").read_text(encoding="utf-8"))
        verified = _date(catalogue.get("verified_on"))
        fresh = verified is not None and 0 <= (as_of-verified).days <= int(catalogue.get("review_after_days", 0))
    except (OSError, ValueError, TypeError):
        return {"available": False, "reason": "Official FD comparison catalogue unavailable", "products": []}
    rows = []
    if fresh:
        for product in catalogue.get("products", []):
            effective = _date(product.get("effective_from"))
            product_verified = _date(product.get("verified_on"))
            rate = _number(product.get("annual_rate_percent"))
            if product.get("status") != "verified" or effective is None or effective > as_of or rate is None or rate < 0:
                continue
            if product_verified is None or not 0 <= (as_of-product_verified).days <= int(product.get("review_after_days", catalogue.get("review_after_days", 0))):
                continue
            rows.append({"id": product["id"], "bank": product["bank"], "tenor_months": product["tenor_months"],
                         "gross_annual_rate_percent": str(rate), "verified_on": product.get("verified_on"),
                         "source_url": product["source_url"], "eligibility_note": product.get("eligibility_note"),
                         "withdrawal_note": product.get("withdrawal_note")})
    return {"available": bool(rows), "catalogue_version": catalogue.get("version"), "verified_on": catalogue.get("verified_on"),
            "products": rows, "scope": "Same official FD catalogue as FIRE. These are alternative term contracts, not promised MF replacement returns or instructions to invest. Eligibility and amount have not been assessed.",
            "reason": None if fresh else "Dated catalogue requires renewed verification",
            "tax_basis": catalogue.get("tax_basis"), "insurance_note": catalogue.get("insurance_note"),
            "future_renewal_rate": None}


def evaluate_mutual_fund_action_checks(
    twin: dict, mutual_fund_payload: dict, *, transactions: list[dict] | None = None,
    tax_payload: dict | None = None, fd_payload: dict | None = None, as_of: date | None = None,
) -> dict:
    """Validate prerequisites after parallel specialists join, never place orders.

    Even complete purchase data cannot price an unspecified future redemption.
    Prospective amounts remain withheld until the dedicated tax engine supports
    that exact class/period and a verified lot-specific disposal scope.
    """
    today = as_of or datetime.now(ZoneInfo("Asia/Kolkata")).date()
    tax = tax_payload or {}
    txns = transactions if transactions is not None else (twin.get("portfolio") or {}).get("transactions") or []
    rows = []
    for fund in mutual_fund_payload.get("funds", []):
        if not isinstance(fund, dict):
            continue
        fid, isin = str(fund.get("fund_id") or fund.get("isin") or "unresolved"), fund.get("isin")
        missing = []
        if fund.get("identity_status") != "verified":
            missing.append("Verified exact scheme, plan and option identity")
        classification = fund.get("tax_classification")
        classification = classification if isinstance(classification, dict) else {}
        category = classification.get("category")
        class_verified = classification.get("verified") is True and category in {"equity_oriented_mf", "specified_mutual_fund", "other_mutual_fund"} and str(classification.get("source_url") or "").startswith("https://") and _date(classification.get("observed_on")) is not None and _date(classification.get("observed_on")) <= today
        if not class_verified:
            missing.append("Official scheme-verified tax classification and applicable-period definition")
        matched = [r for r in txns if isinstance(r, dict) and isin and r.get("isin") == isin]
        purchases = [r for r in matched if str(r.get("txn_type") or r.get("transaction_type") or r.get("type") or "").lower() in {"purchase", "buy", "sip", "switch_in", "switch-in"}]
        dates = [_date(r.get("date") or r.get("txn_date") or r.get("transaction_date")) for r in purchases]
        usable_dates = [d for d in dates if d is not None and d <= today]
        if not purchases or len(usable_dates) != len(purchases):
            missing.append("Complete dated acquisition lots for the relevant units")
        if not purchases or any(_number(r.get("amount")) is None or _number(r.get("units")) is None for r in purchases):
            missing.append("Verified acquisition costs, units and intervening disposal history")
        exit_terms = fund.get("exit_load") or fund.get("exit_terms")
        exit_verified = isinstance(exit_terms, dict) and exit_terms.get("verified") is True and bool(exit_terms.get("source_url"))
        if not exit_verified:
            missing.append("Applicable exit-load schedule and lot-specific eligibility")
        missing.extend(["Prospective redemption date, units and sale value", "Supported lot-mapped tax calculation for this exact class and income period", "Personal residency, income/regime and applicable surcharge/cess context"])
        rows.append({"fund_id":fid,"isin":isin,"status":"conditional_review_only",
                     "tax_estimate_status":"withheld", "estimated_switch_tax":None, "estimated_exit_load":None,
                     "classification_status":"verified" if class_verified else "not_verified",
                     "verified_tax_category":category if class_verified else None, "acquisition_lots_observed":len(purchases),
                     "earliest_observed_acquisition":min(usable_dates).isoformat() if usable_dates else None,
                     "acquisition_periods_observed":sorted({"before_2023_04_01" if d < date(2023,4,1) else "on_or_after_2023_04_01" for d in usable_dates}),
                     "exit_terms_status":"verified_document_required_calculation" if exit_verified else "not_verified",
                     "missing_information":list(dict.fromkeys(missing)),
                     "reason":"Historical classification boundaries depend on verified scheme attributes and dates; no blanket debt-fund short-term rule or equity default is applied. Current-year realized tax is not a prospective switch quote.",
                     "principle_ids":["mf_tax_scope","tax_fund_identity","mf_costs"]})
    return {"version":"mf-action-feasibility-v1","as_of":today.isoformat(),"funds":rows,
            "available":bool(rows),"tax_worker_available":bool(tax.get("available")),
            "tax_rule_version":tax.get("rule_version"), "realized_tax_summary_reused":False,
            "fd_worker_available":bool((fd_payload or {}).get("available")), "fd_comparison":_deposit_context(today),
            "execution_allowed":False,"scope":"Cross-agent feasibility after shared evidence joins. Unknown costs/taxes are not zero; no trade, redemption or change to holdings is executed."}
