#!/usr/bin/env python3
"""Standalone diversification / allocation observation script (NOT wired into the app).

Loads a user's Digital Financial Twin from Postgres, injects condensed guidance from
``.cursor/skills`` (NISM / Psychology of Money / CANSLIM education), and asks
OpenRouter ``inclusionai/ling-3.0-flash-fin`` for educational observations on
concentration, diversification gaps, and category-level allocation ideas.

No live market data is sent — the model reasons from Twin facts + skill rules only.

Usage (from repo root, with venv active)::

    # set OPENROUTER_API_KEY in .env (never commit the key)
    set PYTHONPATH=apps/api
    python scripts/ling_diversification_advice.py --list-users
    python scripts/ling_diversification_advice.py --user-id 1

Optional::

    python scripts/ling_diversification_advice.py --user-id 1 --out advice.json
    python scripts/ling_diversification_advice.py --user-id 1 --dry-run   # print prompt only
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from decimal import Decimal
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = ROOT / ".cursor" / "skills"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "inclusionai/ling-3.0-flash-fin"

# Dev playbooks / verify skills are excluded — finance domain only.
SKILL_NAMES = (
    "nism-investment-adviser-l1",
    "nism-investment-adviser-l2",
    "nism-retirement-adviser",
    "psychology-of-money",
    "canslim-strict-mode",
)


class _JsonEncoder(json.JSONEncoder):
    def default(self, o):  # noqa: ANN001
        if isinstance(o, Decimal):
            return str(o)
        return super().default(o)


def _load_env() -> None:
    load_dotenv(ROOT / ".env")
    load_dotenv(ROOT / "apps" / "web" / ".env.local", override=False)


def _skill_excerpt(path: Path, max_chars: int = 6000) -> str:
    text = path.read_text(encoding="utf-8")
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n[...truncated for prompt size...]\n"


def load_skills() -> str:
    chunks: list[str] = []
    for name in SKILL_NAMES:
        skill_path = SKILLS_DIR / name / "SKILL.md"
        if not skill_path.is_file():
            continue
        chunks.append(f"### Skill: {name}\n{_skill_excerpt(skill_path)}")
    if not chunks:
        raise SystemExit(f"No skills found under {SKILLS_DIR}")
    return "\n\n".join(chunks)


def twin_for_model(twin: dict) -> dict:
    """Strip live market intel and heavy UI map; keep facts the model needs."""
    payload = {
        "user": twin.get("user"),
        "behaviour": twin.get("behaviour"),
        "financial_position": twin.get("financial_position"),
        "portfolio": twin.get("portfolio"),
        "goals": twin.get("goals"),
        "completeness": twin.get("completeness"),
        "dimension_labels": twin.get("dimension_labels"),
        "ready_for_analysis": twin.get("ready_for_analysis"),
        "preanalysis": twin.get("preanalysis"),
    }
    # Explicit: no NSE / opportunity / live prices in this prototype.
    payload["market_data"] = {
        "included": False,
        "note": "Live market data intentionally omitted; reason from Twin facts and skill rules only.",
    }
    return payload


def build_messages(twin_payload: dict, skills: str) -> list[dict[str, str]]:
    system = f"""You are a finance education assistant for AI-CIO (India-focused personal finance).

You receive:
1) A user's Digital Financial Twin (facts from their DB — psychometric scores, cashflow, liabilities, goals, holdings).
2) Condensed domain skills (NISM X-A / X-B, Retirement Adviser, Psychology of Money, CANSLIM Strict Mode education).

Hard constraints (from product + skills):
- Suitability before products: goals, horizon, liquidity, risk capacity first.
- Use ONLY Twin facts; mark missing fields as unknown — never invent balances or holdings.
- Prefer category / asset-class / diversification OBSERVATIONS over ticker-level buy/sell orders.
- Do NOT guarantee returns. Do NOT present anything as risk-free.
- Frame output as educational observations for human review, not execution instructions.
- Behaviour matters: reasonable > theoretically optimal; leave room for error.
- No live market data is provided — do not claim current prices, tips, or "hot" stocks.
- If data is incomplete, say what is missing and how that limits diversification observations.

Output structure (markdown):
1. Snapshot of what is known vs unknown
2. Concentration / diversification observations (asset class, AMC/scheme overlap, equity vs debt, cash buffer)
3. Suitability lens from behaviour + goals (risk, loss aversion, horizon)
4. Category-level ideas the user could *review* for diversification or surplus deployment (e.g. debt funds, index/large-cap, hybrid, emergency buffer, NPS education if retirement goals) — not a shopping list of tickers
5. Risks, tradeoffs, and what to verify next
6. Short disclaimer: not SEBI-registered advice; for education / human review only

Domain skills to obey:
{skills}
"""
    user = (
        "Based on this Twin JSON, explain where diversification looks weak and what "
        "category-level options the user could review to improve resilience or put "
        "idle surplus to work — without live market data.\n\n"
        f"```json\n{json.dumps(twin_payload, cls=_JsonEncoder, indent=2)}\n```"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def list_users() -> None:
    from ai_cio.db.models import User
    from ai_cio.db.session import get_session

    db = get_session()
    try:
        rows = db.query(User).order_by(User.id).all()
        if not rows:
            print("No users in the database.")
            return
        print(f"{'ID':<6} {'NAME':<24} EMAIL")
        for u in rows:
            print(f"{u.id:<6} {(u.name or '')[:24]:<24} {u.email or ''}")
    finally:
        db.close()


def load_twin(user_id: int) -> dict:
    from ai_cio.services.twin import assemble_twin
    from ai_cio.db.session import get_session

    db = get_session()
    try:
        return assemble_twin(db, user_id)
    finally:
        db.close()


def _message_text(message: dict) -> str | None:
    """Pull assistant text from OpenRouter message shapes (incl. reasoning models)."""
    content = message.get("content")
    if isinstance(content, str) and content.strip():
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str) and item.strip():
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if isinstance(text, str) and text.strip():
                    parts.append(text)
        if parts:
            return "\n".join(parts)

    for key in ("reasoning", "reasoning_content"):
        value = message.get(key)
        if isinstance(value, str) and value.strip():
            return value

    return None


def call_openrouter(messages: list[dict[str, str]], model: str, api_key: str) -> str:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/local/ai-cio-ling-advice",
        "X-Title": "AI-CIO Ling diversification prototype",
    }
    body = {
        "model": model,
        "messages": messages,
        "temperature": 0.3,
        # Reasoning models can burn budget on chain-of-thought and return empty content.
        "max_tokens": 8192,
    }
    with httpx.Client(timeout=180.0) as client:
        resp = client.post(OPENROUTER_URL, headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()

    try:
        choice = data["choices"][0]
        message = choice.get("message") or {}
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Unexpected OpenRouter response: {data!r}") from exc

    text = _message_text(message)
    if text:
        return text

    finish = choice.get("finish_reason")
    raise RuntimeError(
        "OpenRouter returned no assistant text "
        f"(finish_reason={finish!r}). Raw message keys: {list(message.keys())}. "
        f"Response snippet: {json.dumps(data)[:800]}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Standalone Ling Flash Fin diversification prototype")
    parser.add_argument("--user-id", type=int, help="Postgres users.id to analyse")
    parser.add_argument("--list-users", action="store_true", help="List users and exit")
    parser.add_argument("--model", default=os.getenv("OPENROUTER_MODEL", DEFAULT_MODEL))
    parser.add_argument("--out", type=Path, help="Optional path to write markdown output")
    parser.add_argument("--dry-run", action="store_true", help="Build prompt only; no API call")
    args = parser.parse_args()

    _load_env()
    if str(ROOT / "apps" / "api") not in sys.path:
        sys.path.insert(0, str(ROOT / "apps" / "api"))

    if args.list_users:
        list_users()
        return 0

    if not args.user_id:
        parser.error("Provide --user-id or --list-users")

    twin = load_twin(args.user_id)
    twin_payload = twin_for_model(twin)
    skills = load_skills()
    messages = build_messages(twin_payload, skills)

    if args.dry_run:
        print(json.dumps({"model": args.model, "messages": messages}, indent=2))
        return 0

    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        print(
            "OPENROUTER_API_KEY is missing. Add it to the repo-root .env file "
            "(see .env.example). Do not commit the key.",
            file=sys.stderr,
        )
        return 1

    print(f"Calling {args.model} for user_id={args.user_id} …", file=sys.stderr)
    advice = call_openrouter(messages, args.model, api_key)

    out_path = args.out or (ROOT / ".dev" / f"ling_advice_user{args.user_id}.md")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(advice, encoding="utf-8")
    print(f"Wrote {out_path}", file=sys.stderr)

    # Windows consoles are often cp1252 — avoid crashing on ₹ / en-dashes.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass
    try:
        print(advice)
    except UnicodeEncodeError:
        sys.stdout.buffer.write(advice.encode("utf-8", errors="replace"))
        sys.stdout.buffer.write(b"\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
