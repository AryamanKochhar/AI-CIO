"""Load condensed domain skills from ``.cursor/skills`` for agent prompts."""
from __future__ import annotations

from pathlib import Path

from ai_cio.settings import ROOT

SKILLS_DIR = ROOT / ".cursor" / "skills"

# Finance domain skills only (exclude pre-commit / tooling playbooks).
DEFAULT_SKILL_NAMES = (
    "nism-investment-adviser-l1",
    "nism-investment-adviser-l2",
    "nism-retirement-adviser",
    "psychology-of-money",
    "canslim-strict-mode",
)

# Shorter pack for the equity decision agent (token budget).
EQUITY_AGENT_SKILL_NAMES = (
    "nism-investment-adviser-l1",
    "psychology-of-money",
    "canslim-strict-mode",
)


def _excerpt(path: Path, max_chars: int = 5000) -> str:
    text = path.read_text(encoding="utf-8")
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n[...truncated for prompt size...]\n"


def load_domain_skills(
    skill_names: tuple[str, ...] = DEFAULT_SKILL_NAMES,
    *,
    max_chars_per_skill: int = 5000,
) -> str:
    chunks: list[str] = []
    for name in skill_names:
        path = SKILLS_DIR / name / "SKILL.md"
        if path.is_file():
            chunks.append(f"### Skill: {name}\n{_excerpt(path, max_chars=max_chars_per_skill)}")
    return "\n\n".join(chunks)


def skill_evidence_stubs(skill_names: tuple[str, ...] = DEFAULT_SKILL_NAMES) -> list[dict[str, str]]:
    """Lightweight evidence rows for UI 'Knowledge used' when skills are injected."""
    rows: list[dict[str, str]] = []
    for name in skill_names:
        path = SKILLS_DIR / name / "SKILL.md"
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        # Prefer first meaningful paragraph after title
        lines = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.startswith("#") and not ln.startswith("---")]
        snippet = " ".join(lines[:3])[:400]
        rows.append(
            {
                "source": "cursor_skill",
                "section": name,
                "reference": str(path.relative_to(ROOT)).replace("\\", "/"),
                "content": snippet or f"Domain skill loaded: {name}",
                "relevance": "equity_decision_framework",
            }
        )
    return rows
