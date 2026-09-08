#!/usr/bin/env python3
"""Dump portfolio pre-analysis JSON for a user (not wired to the LLM call).

Usage (repo root, venv active)::

    set PYTHONPATH=apps/api
    python scripts/dump_portfolio_preanalysis.py --user-id 1
    python scripts/dump_portfolio_preanalysis.py --user-id 1 --out .dev/preanalysis_aryaman.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Dump deterministic portfolio pre-analysis")
    parser.add_argument("--user-id", type=int, required=True)
    parser.add_argument("--out", type=Path, help="Optional output JSON path")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    if str(ROOT / "apps" / "api") not in sys.path:
        sys.path.insert(0, str(ROOT / "apps" / "api"))

    from ai_cio.db.session import configure_engine, get_session
    from ai_cio.services.twin_analytics import build_portfolio_preanalysis

    configure_engine()
    db = get_session()
    try:
        payload = build_portfolio_preanalysis(db, args.user_id)
    finally:
        db.close()

    text = json.dumps(payload, indent=2)
    out = args.out or (ROOT / ".dev" / f"preanalysis_user{args.user_id}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"Wrote {out}", file=sys.stderr)
    # Print a short summary to stdout (full JSON is on disk).
    snap = payload["portfolio_snapshot"]
    print(
        json.dumps(
            {
                "user_id": payload["user_id"],
                "holdings": snap["number_of_holdings"],
                "total_invested_value": snap["total_invested_value"],
                "total_value": snap["total_value"],
                "largest_holding_percent": payload["concentration"]["largest_holding_percent"],
                "top_holdings": [
                    {
                        "name": h["name"],
                        "type": h["instrument_type"],
                        "weight_percent": h["portfolio_weight_percent"],
                        "value": h["value"],
                    }
                    for h in payload["holding_metrics"][:10]
                ],
                "flags": payload["portfolio_flags"],
                "out": str(out),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
