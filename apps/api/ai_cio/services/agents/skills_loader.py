"""Load condensed domain skills from ``.cursor/skills`` for agent prompts."""
from __future__ import annotations

from pathlib import Path
import re

from ai_cio.services.finance_standards import source_context_for_skills

from ai_cio.settings import ROOT

SKILLS_DIR = ROOT / ".cursor" / "skills"

# Finance domain skills only (exclude pre-commit / tooling playbooks).
DEFAULT_SKILL_NAMES = (
    "mutual-fund-first-principles",
    "equity-analysis-first-principles",
    "fd-comparison-first-principles",
    "tax-period-and-fund-classification",
    "trajectory-first-principles",
    "portfolio-first-principles",
    "fire-planning",
    "purchasing-power-and-sequence",
    "fixed-income-first-principles",
    "cost-and-cashflow-first-principles",
    "market-evidence-and-uncertainty",
    "nism-investment-adviser-l1",
    "nism-investment-adviser-l2",
    "nism-retirement-adviser",
    "psychology-of-money",
    "canslim-strict-mode",
    "common-sense-investing",
    "investment-policy-and-risk",
    "liquidity-and-deposit-safety",
    "tax-source-discipline",
)

# Shorter pack for the equity decision agent (token budget).
EQUITY_AGENT_SKILL_NAMES = (
    "equity-analysis-first-principles",
    "portfolio-first-principles",
)


def _excerpt(path: Path, max_chars: int = 5000) -> str:
    text = path.read_text(encoding="utf-8-sig")
    # Descriptions support discovery, not financial reasoning or evidence excerpts.
    text = re.sub(r"\A---\s*\n.*?\n---\s*\n", "", text, count=1, flags=re.DOTALL).strip()
    max_chars = max(0, max_chars)
    if len(text) <= max_chars:
        return text
    excerpt = text[:max_chars]
    # Avoid ending halfway through a source URL or a material condition.
    boundary = excerpt.rfind("\n\n")
    if boundary >= max_chars // 2:
        excerpt = excerpt[:boundary]
    return excerpt + "\n\n[Skill excerpt truncated; use the shared finance review requirements.]\n"


def load_domain_skills(
    skill_names: tuple[str, ...] = DEFAULT_SKILL_NAMES,
    *,
    max_chars_per_skill: int = 5000,
) -> str:
    chunks: list[str] = []
    for name in skill_names:
        if name not in DEFAULT_SKILL_NAMES:
            continue
        path = SKILLS_DIR / name / "SKILL.md"
        if path.is_file():
            chunks.append(f"### Skill: {name}\n{_excerpt(path, max_chars=max_chars_per_skill)}")
    return "\n\n".join(chunks)


def skill_evidence_stubs(skill_names: tuple[str, ...] = DEFAULT_SKILL_NAMES) -> list[dict[str, str]]:
    """Lightweight evidence rows for UI 'Knowledge used' when skills are injected."""
    rows: list[dict[str, str]] = []
    for name in skill_names:
        if name not in DEFAULT_SKILL_NAMES:
            continue
        path = SKILLS_DIR / name / "SKILL.md"
        if not path.is_file():
            continue
        text = _excerpt(path, max_chars=700)
        lines = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.startswith("#")]
        snippet = " ".join(lines[:3])[:400]
        sources = source_context_for_skills((name,))
        source_ids = ", ".join(row["id"] for row in sources)
        rows.append(
            {
                "source": "cursor_skill",
                "section": name,
                "reference": str(path.relative_to(ROOT)).replace("\\", "/"),
                "content": (
                    f"Framework supplied to the analyzer, not proof it was applied. {snippet}"
                    + (f" Source IDs: {source_ids}." if source_ids else " Project/book framework; no official endorsement.")
                ),
                "relevance": "educational_framework_available",
            }
        )
    return rows


_AGENT_ALIASES = {
    "equity": "equity_agent", "mutual_fund": "mutual_fund_agent", "mf": "mutual_fund_agent",
    "fd": "fd_agent", "tax": "tax_agent", "fire": "trajectory_agent", "fire_agent": "trajectory_agent",
    "trajectory": "trajectory_agent", "retirement_agent": "trajectory_agent",
    "portfolio": "portfolio_agent", "orchestrator": "portfolio_agent",
    "coordinator": "portfolio_agent", "orchestration": "portfolio_agent",
}


def agent_resource_pack(agent_id: str) -> dict:
    """Scoped availability metadata; applied principles are verified separately.

    Resource IDs are deterministic manifest metadata, never model-authored sources.
    Books are bibliographic context only when complete text is unavailable.
    """
    from ai_cio.services.finance_standards import load_source_manifest
    from ai_cio.services.skill_principles import PRINCIPLES, applied_principles

    canonical = _AGENT_ALIASES.get(agent_id, agent_id)
    manifest = load_source_manifest()
    spec = manifest.get("agent_resource_packs", {}).get(canonical)
    if not isinstance(spec, dict):
        return {"agent_id": canonical, "skill_names": [], "source_ids": [], "resources": [],
                "principles": [], "scope": "No registered specialist resource pack"}
    names = tuple(n for n in spec.get("skill_names", []) if n in DEFAULT_SKILL_NAMES)
    allowed = set(spec.get("source_ids", []))
    resources = [row for row in source_context_for_skills(names) if row["id"] in allowed]
    source_ids = [row["id"] for row in resources]
    principles = applied_principles([pid for pid, (skill, _, _) in PRINCIPLES.items() if skill in names])
    return {
        "agent_id": canonical, "skill_names": list(names), "source_ids": source_ids,
        "resources": resources, "principles": principles,
        "portfolio_source_ids": list(manifest.get("agent_resource_packs", {}).get("portfolio_agent", {}).get("source_ids", [])),
        "scope": "Scoped frameworks supplied to this specialist; availability is not proof of application. Only accepted findings identify applied exact-section principles. Book metadata is not text evidence.",
    }


def load_agent_skills(agent_id: str, *, max_chars_per_skill: int = 5000) -> str:
    """Supply the worker's own guides and the shared portfolio constraints."""
    pack = agent_resource_pack(agent_id)
    return load_domain_skills(tuple(pack["skill_names"]), max_chars_per_skill=max_chars_per_skill)
