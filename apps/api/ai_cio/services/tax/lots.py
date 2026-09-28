"""Tax-lot construction from portfolio holdings + transactions.

Source of truth remains Holding/Transaction rows — lots are derived views.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from ai_cio.services.tax.rules import (
    AssetCategory,
    classify_asset,
    get_rules,
    holding_classification,
)

ZERO = Decimal("0")


def _dec(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _parse_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    raw = str(value).strip()[:10]
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _is_buy(txn_type: str | None, description: str | None) -> bool:
    t = f"{txn_type or ''} {description or ''}".upper()
    return any(
        k in t
        for k in (
            "PURCHASE",
            "BUY",
            "SIP",
            "CREDIT",
            "ALLOTMENT",
            "SWITCH IN",
            "SWITCH-IN",
            "REINVEST",
        )
    )


def _is_sell(txn_type: str | None, description: str | None) -> bool:
    t = f"{txn_type or ''} {description or ''}".upper()
    return any(k in t for k in ("REDEEM", "SELL", "DEBIT", "SWITCH OUT", "SWITCH-OUT"))


@dataclass
class OpenLot:
    key: str
    isin: str | None
    name: str
    asset_category: AssetCategory
    qty: Decimal
    unit_cost: Decimal | None
    acquisition_date: date | None
    source_txn_ids: list[str] = field(default_factory=list)
    cost_basis_status: str = "ok"  # ok | insufficient_data | inferred_holding


def build_tax_lots(
    holdings: list[dict[str, Any]],
    transactions: list[dict[str, Any]],
    *,
    as_of: date | None = None,
    financial_year: str | None = None,
) -> dict[str, Any]:
    as_of = as_of or date.today()
    rules = get_rules(financial_year)
    open_lots: list[OpenLot] = []
    realized: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    data_quality = {"total_holdings": len(holdings), "usable_cost_lots": 0, "insufficient": 0}

    # Index buys/sells by (isin or scheme+amc)
    by_key: dict[str, list[dict[str, Any]]] = {}
    for i, txn in enumerate(transactions):
        isin = (txn.get("isin") or "").strip() or None
        name = txn.get("scheme_name") or "Unknown"
        amc = txn.get("amc") or ""
        key = isin or f"{amc}|{name}"
        row = dict(txn)
        row["_idx"] = i
        by_key.setdefault(key, []).append(row)

    # Process FIFO per security from transactions
    for key, txns in by_key.items():
        txns_sorted = sorted(txns, key=lambda t: (_parse_date(t.get("date")) or date.min, t.get("_idx", 0)))
        queue: list[OpenLot] = []
        sample = txns_sorted[0]
        category = classify_asset(
            asset_class=None,
            scheme_name=sample.get("scheme_name"),
            amc=sample.get("amc"),
        )
        # Equity demat CREDIT/DEBIT usually lack NAV — skip lot math, mark later via holdings
        equity_like = category == "listed_equity" or sample.get("amc") == "EQUITY"

        for txn in txns_sorted:
            qty = _dec(txn.get("units")) or ZERO
            if qty <= 0:
                continue
            nav = _dec(txn.get("nav"))
            amount = _dec(txn.get("amount"))
            d = _parse_date(txn.get("date"))
            txn_id = f"txn:{txn.get('_idx')}:{txn.get('date')}:{txn.get('transaction_type')}"

            if equity_like and nav is None:
                # Cannot safely build price from stamp-duty amount
                continue

            if _is_buy(txn.get("transaction_type"), txn.get("description")):
                unit_cost = nav
                if unit_cost is None and amount is not None and qty > 0:
                    unit_cost = (amount / qty).quantize(Decimal("0.0001"))
                if unit_cost is None:
                    missing.append(
                        {
                            "security": sample.get("scheme_name"),
                            "isin": sample.get("isin"),
                            "reason": "missing_acquisition_price",
                            "transaction_id": txn_id,
                        }
                    )
                    continue
                queue.append(
                    OpenLot(
                        key=key,
                        isin=sample.get("isin"),
                        name=sample.get("scheme_name") or key,
                        asset_category=category,
                        qty=qty,
                        unit_cost=unit_cost,
                        acquisition_date=d,
                        source_txn_ids=[txn_id],
                    )
                )
            elif _is_sell(txn.get("transaction_type"), txn.get("description")):
                sell_price = nav
                if sell_price is None and amount is not None and qty > 0:
                    sell_price = (amount / qty).quantize(Decimal("0.0001"))
                remaining = qty
                while remaining > 0 and queue:
                    lot = queue[0]
                    take = min(lot.qty, remaining)
                    cost = (lot.unit_cost or ZERO) * take
                    proceeds = (sell_price or ZERO) * take if sell_price is not None else None
                    if proceeds is None or lot.unit_cost is None or lot.acquisition_date is None:
                        missing.append(
                            {
                                "security": lot.name,
                                "isin": lot.isin,
                                "reason": "insufficient_data_on_sale",
                                "transaction_id": txn_id,
                            }
                        )
                        break
                    gain = proceeds - cost
                    klass = holding_classification(
                        category=lot.asset_category,
                        acquisition=lot.acquisition_date,
                        disposal_or_as_of=d or as_of,
                        rules=rules,
                    )
                    realized.append(
                        {
                            "security": lot.name,
                            "isin": lot.isin,
                            "qty": f"{take:.4f}",
                            "acquisition_date": lot.acquisition_date.isoformat(),
                            "sale_date": (d or as_of).isoformat(),
                            "cost_basis": f"{cost:.2f}",
                            "sale_value": f"{proceeds:.2f}",
                            "gain_loss": f"{gain:.2f}",
                            "term": klass.get("term"),
                            "holding_days": klass.get("holding_days"),
                            "classification_status": klass.get("status"),
                            "asset_category": lot.asset_category,
                            "source_transaction_ids": lot.source_txn_ids + [txn_id],
                            "rule_version": rules.version,
                        }
                    )
                    lot.qty -= take
                    remaining -= take
                    if lot.qty <= 0:
                        queue.pop(0)
                if remaining > 0 and sell_price is not None:
                    missing.append(
                        {
                            "security": sample.get("scheme_name"),
                            "isin": sample.get("isin"),
                            "reason": "sale_exceeds_known_lots",
                            "remaining_qty": f"{remaining:.4f}",
                        }
                    )
        open_lots.extend(queue)

    # Holdings without reconstructed lots — use invested_amount aggregate if present
    open_by_isin = {(l.isin or l.key): l for l in open_lots}
    for h in holdings:
        isin = (h.get("isin") or "").strip() or None
        name = h.get("scheme_name") or "Unknown"
        amc = h.get("amc") or ""
        key = isin or f"{amc}|{name}"
        qty = _dec(h.get("closing_units")) or ZERO
        if qty <= 0:
            continue
        category = classify_asset(
            asset_class=h.get("asset_class"),
            scheme_name=name,
            amc=amc,
        )
        if key in open_by_isin or any(l.key == key for l in open_lots):
            continue
        invested = _dec(h.get("invested_amount"))
        nav = _dec(h.get("nav"))
        if invested is not None and invested > 0 and qty > 0:
            unit_cost = (invested / qty).quantize(Decimal("0.0001"))
            open_lots.append(
                OpenLot(
                    key=key,
                    isin=isin,
                    name=name,
                    asset_category=category,
                    qty=qty,
                    unit_cost=unit_cost,
                    acquisition_date=None,
                    source_txn_ids=[f"holding:{key}"],
                    cost_basis_status="inferred_holding",
                )
            )
            data_quality["usable_cost_lots"] += 1
            missing.append(
                {
                    "security": name,
                    "isin": isin,
                    "reason": "acquisition_date_unknown_using_invested_amount",
                    "note": "Term classification cannot be determined without buy date.",
                }
            )
        else:
            data_quality["insufficient"] += 1
            missing.append(
                {
                    "security": name,
                    "isin": isin,
                    "reason": "missing_acquisition_cost",
                    "asset_category": category,
                    "qty": f"{qty:.4f}",
                    "market_value": f"{(_dec(h.get('valuation') or ZERO) or ZERO):.2f}",
                }
            )

    # Unrealized on open lots
    holding_price = {}
    for h in holdings:
        isin = (h.get("isin") or "").strip() or None
        key = isin or f"{h.get('amc')}|{h.get('scheme_name')}"
        holding_price[key] = _dec(h.get("nav"))

    unrealized: list[dict[str, Any]] = []
    for lot in open_lots:
        price = holding_price.get(lot.key) or holding_price.get(lot.isin or "")
        if lot.unit_cost is None or price is None:
            data_quality["insufficient"] += 1
            continue
        cost = lot.unit_cost * lot.qty
        value = price * lot.qty
        gain = value - cost
        klass = holding_classification(
            category=lot.asset_category,
            acquisition=lot.acquisition_date,
            disposal_or_as_of=as_of,
            rules=rules,
        )
        if lot.cost_basis_status == "ok" and lot.acquisition_date:
            data_quality["usable_cost_lots"] += 1
        unrealized.append(
            {
                "security": lot.name,
                "isin": lot.isin,
                "qty": f"{lot.qty:.4f}",
                "unit_cost": f"{lot.unit_cost:.4f}",
                "current_price": f"{price:.4f}",
                "cost_basis": f"{cost:.2f}",
                "market_value": f"{value:.2f}",
                "unrealized_gain_loss": f"{gain:.2f}",
                "acquisition_date": lot.acquisition_date.isoformat() if lot.acquisition_date else None,
                "term": klass.get("term"),
                "holding_days": klass.get("holding_days"),
                "days_to_long_term": klass.get("days_to_long_term"),
                "classification_status": klass.get("status"),
                "asset_category": lot.asset_category,
                "cost_basis_status": lot.cost_basis_status,
                "source_transaction_ids": lot.source_txn_ids,
                "rule_version": rules.version,
            }
        )

    return {
        "as_of": as_of.isoformat(),
        "rule_version": rules.version,
        "financial_year": rules.financial_year,
        "realized_lots": realized,
        "unrealized_lots": unrealized,
        "missing_data": missing,
        "data_quality": data_quality,
    }
