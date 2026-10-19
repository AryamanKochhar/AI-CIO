"""Source-bounded educational context; never a tax/rate or suitability engine."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import json
from typing import Any
from zoneinfo import ZoneInfo

from ai_cio.settings import ROOT

SOURCE_MANIFEST = ROOT / "knowledge" / "finance_sources.json"
REVIEW_STRUCTURE = (
    "observed facts with source/date and denominator",
    "why the facts matter for recorded goals or constraints",
    "conditional review options, including leaving the position unchanged when relevant",
    "material liquidity, risk, cost and tax trade-offs",
    "specific review action and the input it will verify",
    "supplied source IDs, assumptions and missing information",
)


def load_source_manifest() -> dict[str, Any]:
    """Missing/corrupt metadata must not manufacture authoritative sources."""
    try:
        data = json.loads(SOURCE_MANIFEST.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {"version": "unavailable", "sources": [], "skill_sources": {}}
    return data if isinstance(data, dict) else {"version": "unavailable", "sources": []}


def source_context_for_skills(skill_names: tuple[str, ...], *, as_of: date | None = None) -> list[dict[str, Any]]:
    manifest = load_source_manifest()
    selected = {sid for name in skill_names for sid in manifest.get("skill_sources", {}).get(name, [])}
    today = as_of or datetime.now(ZoneInfo("Asia/Kolkata")).date()
    rows = []
    for source in manifest.get("sources", []):
        if not isinstance(source, dict) or source.get("id") not in selected:
            continue
        try:
            verified = date.fromisoformat(source["verified_on"])
            age = (today - verified).days
            due = age < 0 or age > int(source["review_after_days"])
        except (KeyError, TypeError, ValueError):
            due = True
        rows.append({**source, "review_due": due, "role": "educational_context_not_user_fact_or_rate_table"})
    return rows


def _amount_known(field: Any) -> bool:
    if not isinstance(field, dict) or field.get("known") is False:
        return False
    raw = field.get("value")
    if raw is None or isinstance(raw, bool):
        return False
    try:
        return Decimal(str(raw)).is_finite()
    except (InvalidOperation, ValueError):
        return False


def build_finance_review_context(twin: dict[str, Any], skill_names: tuple[str, ...]) -> dict[str, Any]:
    """Report input coverage, without estimating a risk score or inventing inputs."""
    position = twin.get("financial_position") or {}
    behaviour = twin.get("behaviour") or {}
    goals = (twin.get("goals") or {}).get("items") or []
    holdings = (twin.get("portfolio") or {}).get("holdings") or []
    missing = []
    known = [name for name in ("income", "expenses", "liquid") if _amount_known(position.get(name))]
    for name in ("income", "expenses", "liquid"):
        if name not in known:
            missing.append(f"Recorded {name} amount is missing or unusable; financial capacity is not fully evaluated.")
    if behaviour.get("status") != "known":
        missing.append("A completed declared-risk assessment is missing; do not infer willingness from demographics.")
    if not goals:
        missing.append("Goal amount, date and priority are not recorded; goal-specific suitability is not evaluated.")
    elif any(not (g.get("target_date") or g.get("horizon_years")) for g in goals if isinstance(g, dict)):
        missing.append("At least one recorded goal lacks a usable date/horizon; do not invent its deadline.")
    if not holdings:
        missing.append("No holdings are recorded in scope; do not describe a position, allocation or sector as observed.")
    unconfirmed = [name for name in ("income_stability", "essential_expenses", "dependants", "insurance") if position.get(name) is None]
    if unconfirmed:
        missing.append(f"Loss-capacity inputs require confirmation: {', '.join(unconfirmed)}.")
    missing.append("Costs, acquisition dates/cost basis and applicable tax-rule coverage must be checked before evaluating transaction consequences.")
    sources = source_context_for_skills(skill_names)
    overdue = [row["id"] for row in sources if row["review_due"]]
    if overdue:
        missing.append(f"Source context requires renewed verification before current-rule conclusions: {', '.join(overdue)}.")
    return {
        "version": "finance-review-v1",
        "review_structure": list(REVIEW_STRUCTURE),
        "known_amount_fields": known,
        "required_missing_information": missing,
        "risk_capacity_status": "not_fully_assessed",
        "declared_willingness_status": "recorded" if behaviour.get("status") == "known" else "unknown",
        "source_context": sources,
        "source_review_due": overdue,
        "numeric_authority": "Twin facts and deterministic services only; no legal rates or outcome probabilities inferred from these sources",
    }


def resolve_model_knowledge_claims(claims: Any, allowed: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Resolve supplied IDs to our metadata, never accept model-authored URLs/facts."""
    if not isinstance(claims, list):
        return []
    indexed = {str(row["id"]): row for row in allowed}
    resolved = []
    seen = set()
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        sid = claim.get("source_id")
        if not isinstance(sid, str) or sid not in indexed or sid in seen:
            continue
        row = indexed[sid]
        seen.add(sid)
        resolved.append({
            "source": str(row["publisher"]), "section": sid, "reference": str(row["url"]),
            "content": f"Educational context supplied; model identified it as relevant, not independently verified use. {row['scope']} Verified {row['verified_on']}; review_due={row['review_due']}.",
            "relevance": "model_selected_supplied_source",
        })
    return resolved
