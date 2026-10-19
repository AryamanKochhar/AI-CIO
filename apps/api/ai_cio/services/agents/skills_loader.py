"""Load condensed domain skills from ``.cursor/skills`` for agent prompts."""
from __future__ import annotations

from pathlib import Path
import re

from ai_cio.services.finance_standards import source_context_for_skills

from ai_cio.settings import ROOT

SKILLS_DIR = ROOT / ".cursor" / "skills"

# Finance domain skills only (exclude pre-commit / tooling playbooks).
DEFAULT_SKILL_NAMES = (
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
    "nism-investment-adviser-l1",
    "psychology-of-money",
    "canslim-strict-mode",
    "common-sense-investing",
    "investment-policy-and-risk",
    "nism-retirement-adviser",
    "liquidity-and-deposit-safety",
    "tax-source-discipline",
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
