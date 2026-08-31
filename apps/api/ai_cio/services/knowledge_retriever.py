"""Authoritative knowledge retrieval — keyword-based MVP."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ai_cio.settings import KNOWLEDGE_DIR

TOPIC_FILES = {
    "concentration": "concentration.md",
    "diversification": "diversification.md",
    "allocation": "asset_allocation.md",
    "asset_allocation": "asset_allocation.md",
    "portfolio": "portfolio_management.md",
    "mutual_fund": "mutual_funds.md",
    "sector": "diversification.md",
    "risk": "portfolio_management.md",
}


def retrieve_knowledge(*, topics: list[str], limit: int = 3) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
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
        refs.append(
            {
                "source": "knowledge",
                "title": fname.replace("_", " ").replace(".md", "").title(),
                "section": topic,
                "version": "local",
                "reference": str(path.relative_to(KNOWLEDGE_DIR.parent)),
                "text": excerpt,
            }
        )
        if len(refs) >= limit:
            break
    return refs
