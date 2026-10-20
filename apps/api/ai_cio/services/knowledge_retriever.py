"""Authoritative knowledge retrieval — keyword-based MVP."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ai_cio.settings import KNOWLEDGE_DIR
from ai_cio.services.finance_standards import load_source_manifest

TOPIC_FILES = {
    "inflation": "real_returns.md",
    "real_return": "real_returns.md",
    "sequence_risk": "sequence_risk.md",
    "bond": "bond_risks.md",
    "fixed_income": "bond_risks.md",
    "fees": "fee_drag.md",
    "costs": "fee_drag.md",
    "investment_budget": "cashflow_commitment.md",
    "covariance": "covariance_and_risk.md",
    "uncertainty": "covariance_and_risk.md",

    "concentration": "concentration.md",
    "diversification": "diversification.md",
    "allocation": "asset_allocation.md",
    "asset_allocation": "asset_allocation.md",
    "portfolio": "portfolio_management.md",
    "mutual_fund": "mutual_funds.md",
    "sector": "diversification.md",
    "risk": "portfolio_management.md",
    "liquidity": "liquidity.md",
    "emergency": "liquidity.md",
    "fd": "liquidity.md",
    "retirement": "retirement.md",
    "goals": "goal_priorities.md",
    "goal": "goal_priorities.md",
    "tax": "tax_context.md",
}


def retrieve_knowledge(*, topics: list[str], limit: int = 3) -> list[dict[str, Any]]:
    if limit <= 0:
        return []
    manifest = load_source_manifest()
    sources = {row["id"]: row for row in manifest.get("sources", []) if isinstance(row, dict) and "id" in row}
    refs: list[dict[str, Any]] = []
    seen: set[str] = set()
    for topic in topics:
        fname = TOPIC_FILES.get(topic.lower())
        if not fname or fname in seen:
            continue
        path = KNOWLEDGE_DIR / fname
        if not path.exists():
            continue
        seen.add(fname)
        text = path.read_text(encoding="utf-8")
        excerpt = "\n".join(text.strip().splitlines()[:12])
        source_ids = manifest.get("knowledge_sources", {}).get(fname, [])
        source_rows = [sources[sid] for sid in source_ids if sid in sources]
        for row in source_rows:
            excerpt += f"\nEducational source [{row['id']}]: {row['publisher']}, {row['title']}; {row['url']} (verified {row['verified_on']}; {row['edition_or_effective_scope']})."
        refs.append(
            {
                "source": "knowledge",
                "title": fname.replace("_", " ").replace(".md", "").title(),
                "section": topic,
                "version": manifest.get("version", "unavailable"),
                "source_ids": [row["id"] for row in source_rows],
                "reference": str(path.relative_to(KNOWLEDGE_DIR.parent)),
                "text": excerpt,
            }
        )
        if len(refs) >= limit:
            break
    return refs
