"""Versioned Indian capital-gains tax rules for AI-CIO.

Deterministic only — no LLM. Rules are FY-scoped and auditable.
Default: FY 2025-26 / AY 2026-27 special rates as commonly notified
(STCG u/s 111A 20%, LTCG u/s 112A 12.5% with ₹1.25L threshold for equity/EO MF).

This is an analytical engine, not tax advice.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

AssetCategory = Literal[
    "listed_equity",
    "equity_oriented_mf",
    "debt_oriented_mf",
    "other",
    "unknown",
]


@dataclass(frozen=True)
class TaxRuleVersion:
    financial_year: str  # e.g. "2025-26"
    assessment_year: str  # e.g. "2026-27"
    version: str
    equity_lt_days: int
    equity_stcg_rate: Decimal  # section 111A
    equity_ltcg_rate: Decimal  # section 112A
    equity_ltcg_exemption: Decimal  # 112A threshold
    debt_mf_always_short_term: bool
    stcl_offsets_stcg: bool
    stcl_offsets_ltcg: bool
    ltcl_offsets_ltcg_only: bool
    carry_forward_years: int
    notes: tuple[str, ...]


FY_2025_26 = TaxRuleVersion(
    financial_year="2025-26",
    assessment_year="2026-27",
    version="fy2025-26.v1",
    equity_lt_days=365,  # 12 months for listed equity / equity-oriented MF
    equity_stcg_rate=Decimal("0.20"),
    equity_ltcg_rate=Decimal("0.125"),
    equity_ltcg_exemption=Decimal("125000"),
    debt_mf_always_short_term=True,
    stcl_offsets_stcg=True,
    stcl_offsets_ltcg=True,
    ltcl_offsets_ltcg_only=True,
    carry_forward_years=8,
    notes=(
        "Listed equity / equity-oriented MF: LTCG after 12 months.",
        "STCG u/s 111A and LTCG u/s 112A rates as configured for AY 2026-27.",
        "Debt-oriented MF treated as short-term for this engine version.",
        "STCL may offset STCG and LTCG; LTCL offsets LTCG only.",
        "Analytical estimate — not tax advice.",
    ),
)

_REGISTRY: dict[str, TaxRuleVersion] = {
    FY_2025_26.financial_year: FY_2025_26,
    "current": FY_2025_26,
}


def get_rules(financial_year: str | None = None) -> TaxRuleVersion:
    key = (financial_year or "current").strip()
    if key not in _REGISTRY:
        return FY_2025_26
    return _REGISTRY[key]


def current_financial_year(as_of: date | None = None) -> str:
    d = as_of or date.today()
    if d.month >= 4:
        start = d.year
    else:
        start = d.year - 1
    return f"{start}-{str(start + 1)[-2:]}"


def fy_bounds(financial_year: str) -> tuple[date, date]:
    start_year = int(financial_year.split("-")[0])
    return date(start_year, 4, 1), date(start_year + 1, 3, 31)


def classify_asset(
    *,
    asset_class: str | None,
    scheme_name: str | None,
    amc: str | None,
) -> AssetCategory:
    ac = (asset_class or "").lower()
    name = f"{scheme_name or ''} {amc or ''}".upper()
    if ac == "equity" or amc == "EQUITY":
        return "listed_equity"
    if any(tok in name for tok in ("DEBT", "LIQUID", "GILT", "OVERNIGHT", "MONEY MARKET", "ARBITRAGE")):
        # Arbitrage often equity-oriented for tax — keep as EO MF if "ARBITRAGE" alone is weak;
        # treat explicit debt tokens as debt.
        if "ARBITRAGE" in name and "DEBT" not in name:
            return "equity_oriented_mf"
        return "debt_oriented_mf"
    if ac in {"mutual_fund", "mf", ""} or "FUND" in name or "GROWTH" in name:
        return "equity_oriented_mf"
    if not ac and not scheme_name:
        return "unknown"
    return "other"


def holding_classification(
    *,
    category: AssetCategory,
    acquisition: date | None,
    disposal_or_as_of: date,
    rules: TaxRuleVersion,
) -> dict:
    if acquisition is None:
        return {
            "status": "insufficient_data",
            "term": None,
            "holding_days": None,
            "missing": ["acquisition_date"],
            "rule_version": rules.version,
        }
    days = (disposal_or_as_of - acquisition).days
    if category in {"listed_equity", "equity_oriented_mf"}:
        term = "long_term" if days >= rules.equity_lt_days else "short_term"
        days_to_lt = max(0, rules.equity_lt_days - days) if term == "short_term" else 0
        return {
            "status": "ok",
            "term": term,
            "holding_days": days,
            "days_to_long_term": days_to_lt,
            "rule_version": rules.version,
            "category": category,
        }
    if category == "debt_oriented_mf" and rules.debt_mf_always_short_term:
        return {
            "status": "ok",
            "term": "short_term",
            "holding_days": days,
            "days_to_long_term": None,
            "rule_version": rules.version,
            "category": category,
        }
    return {
        "status": "insufficient_data",
        "term": None,
        "holding_days": days,
        "missing": ["unsupported_asset_category"],
        "rule_version": rules.version,
        "category": category,
    }


def estimate_equity_tax(
    *,
    stcg: Decimal,
    ltcg: Decimal,
    stcl: Decimal,
    ltcl: Decimal,
    rules: TaxRuleVersion,
) -> dict:
    """Simplified set-off then special-rate estimate (no surcharge/cess slabs)."""
    # Set off STCL against STCG then LTCG
    rem_stcl = stcl
    taxable_stcg = stcg
    if rem_stcl > 0 and taxable_stcg > 0:
        use = min(rem_stcl, taxable_stcg)
        taxable_stcg -= use
        rem_stcl -= use
    taxable_ltcg = ltcg
    if rem_stcl > 0 and taxable_ltcg > 0:
        use = min(rem_stcl, taxable_ltcg)
        taxable_ltcg -= use
        rem_stcl -= use
    # LTCL only vs LTCG
    rem_ltcl = ltcl
    if rem_ltcl > 0 and taxable_ltcg > 0:
        use = min(rem_ltcl, taxable_ltcg)
        taxable_ltcg -= use
        rem_ltcl -= use

    stcg_tax = (taxable_stcg * rules.equity_stcg_rate).quantize(Decimal("0.01"))
    ltcg_after_exemption = max(Decimal("0"), taxable_ltcg - rules.equity_ltcg_exemption)
    ltcg_tax = (ltcg_after_exemption * rules.equity_ltcg_rate).quantize(Decimal("0.01"))
    total = stcg_tax + ltcg_tax
    return {
        "taxable_stcg": f"{taxable_stcg:.2f}",
        "taxable_ltcg_before_exemption": f"{taxable_ltcg:.2f}",
        "ltcg_exemption_applied": f"{min(taxable_ltcg, rules.equity_ltcg_exemption):.2f}",
        "taxable_ltcg_after_exemption": f"{ltcg_after_exemption:.2f}",
        "estimated_stcg_tax": f"{stcg_tax:.2f}",
        "estimated_ltcg_tax": f"{ltcg_tax:.2f}",
        "estimated_capital_gains_tax": f"{total:.2f}",
        "unused_stcl": f"{rem_stcl:.2f}",
        "unused_ltcl": f"{rem_ltcl:.2f}",
        "rule_version": rules.version,
        "assumptions": [
            "Ignores surcharge/cess and slab-rate income interactions.",
            "Applies 112A exemption pool once at portfolio level for equity/EO MF LTCG.",
            "Analytical estimate — not tax advice.",
        ],
        "rates": {
            "stcg": f"{rules.equity_stcg_rate}",
            "ltcg": f"{rules.equity_ltcg_rate}",
            "ltcg_exemption": f"{rules.equity_ltcg_exemption:.2f}",
        },
    }
