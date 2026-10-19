r"""Idempotently seed all three synthetic scenarios, using Dhan daily data.

Run with the configured development .env, never a real broker portfolio import:
  .venv\Scripts\python.exe scripts/seed_demo_personas.py --upgrade-demo-sessions
Use --offline to keep explicitly synthetic reference valuations.
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from ai_cio.db.models import Document, FixedDeposit, Fund, Goal, Holding, Transaction, User
from ai_cio.db.session import get_session
from ai_cio.services.demo_personas import launch_persona, persona_catalogue
from ai_cio.services.demo_scenarios import populate_financial_scenario
from ai_cio.services.holding_market_data import build_holding_market_data, instrument_catalogue, cached_history
from decimal import Decimal
from ai_cio.services.instruments import seed_instrument


def seed_all(db, *, upgrade_demo_sessions=False) -> list[dict]:
    seed_instrument(db)
    catalogue = persona_catalogue(db)
    output = []
    for persona in catalogue:
        email = f"demo+{persona['id']}@ai-cio.local"
        user = db.query(User).filter(User.email == email).one_or_none()
        if user is None:
            result = launch_persona(db, persona["id"])
            user = result["user"]
            user.email = email
        if upgrade_demo_sessions:
            candidates = db.query(User).filter(User.name == f"{persona['name']} (synthetic demo)").all()
            for candidate in candidates:
                docs = db.query(Document).filter(Document.user_id == candidate.id).all()
                if len(docs) != 1:
                    continue
                doc = docs[0]
                meta = doc.metadata_json or {}
                if doc.kind != "demo_portfolio" or not meta.get("synthetic") or meta.get("persona") != persona["id"] or meta.get("fixture_version", 1) != 1:
                    continue
                if db.query(Transaction).filter(Transaction.user_id == candidate.id).count() or db.query(FixedDeposit).filter(FixedDeposit.user_id == candidate.id).count():
                    continue
                old_goals = db.query(Goal).filter(Goal.user_id == candidate.id).all()
                if any(g.notes != "Synthetic demo assumption; not a real client's goal." for g in old_goals):
                    continue
                db.query(Holding).filter(Holding.document_id == doc.id).delete(synchronize_session=False)
                db.query(Fund).filter(Fund.document_id == doc.id).delete(synchronize_session=False)
                db.query(Goal).filter(Goal.user_id == candidate.id).delete(synchronize_session=False)
                db.delete(doc)
                db.flush()
                populate_financial_scenario(db, candidate.id, persona)
        demo_doc = db.query(Document).filter(Document.user_id == user.id, Document.kind == "demo_portfolio").first()
        if demo_doc and (demo_doc.metadata_json or {}).get("synthetic"):
            mapping = {item["isin"]: item for item in instrument_catalogue()}
            for holding, fund in db.query(Holding, Fund).join(Fund, Holding.fund_id == Fund.id).filter(Holding.document_id == demo_doc.id):
                item = mapping.get(fund.isin)
                history = cached_history("NSE_EQ", item["security_id"]) if item else None
                if history:
                    holding.nav = Decimal(str(history["close"][-1]))
                    holding.valuation = holding.nav * holding.closing_units
                    holding.valuation_date = history["as_of"]
                    if holding.invested_amount:
                        holding.unrealised_pl = holding.valuation - holding.invested_amount
                        holding.unrealised_pl_pct = (holding.valuation / holding.invested_amount - 1) * 100
        output.append({"persona": persona["id"], "user_id": user.id,
            "holdings": db.query(Holding).filter(Holding.user_id == user.id).count(),
            "transactions": db.query(Transaction).filter(Transaction.user_id == user.id).count(),
            "goals": db.query(Goal).filter(Goal.user_id == user.id).count(),
            "fixed_deposits": db.query(FixedDeposit).filter(FixedDeposit.user_id == user.id).count()})
    db.flush()
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--upgrade-demo-sessions", action="store_true")
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)  # Never print provider authentication responses.
    market = {"available": False, "reason": "Explicit offline fixture values"}
    if not args.offline:
        market = build_holding_market_data({"portfolio": {"holdings": [{"isin": item["isin"], "asset_class": "equity"} for item in instrument_catalogue()]}})
    with get_session() as db:
        seeded = seed_all(db, upgrade_demo_sessions=args.upgrade_demo_sessions)
        db.commit()
    print(json.dumps({"synthetic_personas": seeded, "market_available": market.get("available"),
        "market_reason": market.get("reason"), "market_holdings": [{"symbol": row["symbol"], "as_of": row["as_of"], "candles": row["candles"]} for row in market.get("holdings", [])]}, indent=2))


if __name__ == "__main__":
    main()
