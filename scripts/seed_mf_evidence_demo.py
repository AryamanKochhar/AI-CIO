"""Create one explicitly synthetic MF account; never modify existing portfolios.

Run from the repository with its configured development database. Holdings are
invented quantities in real schemes; public NAV/disclosures are dated evidence.
No purchases, redemptions, broker calls or complete cashflow history are implied.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api"))

from ai_cio.db.models import Document, Fund, Holding, User
from ai_cio.db.session import get_session
from ai_cio.services import assessments, finances, goals, identity, journey
from ai_cio.services.demo_personas import persona_catalogue
from ai_cio.services.mutual_funds.provider import MutualFundProvider

NAME = "MF evidence demo (synthetic demo)"
SEED = "mf-evidence-demo-v1"
FUNDS = [("INF879O01027", "Parag Parikh Flexi Cap Fund - Direct Plan Growth", "1000"),
         ("INF879O01100", "Parag Parikh ELSS Tax Saver Fund - Direct Plan", "1500"),
         ("INF200K01T51", "SBI Small Cap Fund Direct Growth", "2000")]


def create_demo():
    with get_session() as db:
        existing = db.query(User).filter(User.name == NAME).first()
        if existing:
            document = db.query(Document).filter(Document.user_id == existing.id, Document.kind == "demo_portfolio").first()
            if not document or (document.metadata_json or {}).get("seed") != SEED:
                raise RuntimeError("An unrelated account has the reserved demo name; nothing changed")
            return {"user_id": existing.id, "name": NAME, "created": False, "synthetic": True}
        # Acquire the dated public inputs first. Failed acquisition must not leave
        # an incomplete account or invented NAV in the development database.
        provider = MutualFundProvider(allow_network=True)
        provider.begin_run()
        positions = []
        for isin, name, units in FUNDS:
            resolved = provider.resolve({"isin": isin, "scheme_name": name})
            if resolved["identity_status"] != "verified":
                raise RuntimeError("The demo scheme identity is unavailable; no account was created")
            history = provider.history(resolved, as_of=date.today())
            points = history.get("points") or []
            if not points:
                raise RuntimeError("Dated public NAV unavailable; no account was created")
            latest = max(points, key=lambda row: row["date"])
            positions.append((resolved, units, latest, history.get("source_url")))
        user = identity.create_user(db, NAME)
        maya = next(row for row in persona_catalogue(db) if row["id"] == "maya")
        assessment = assessments.start_assessment(db, user.id)
        for answer in maya["fixed_answers"]:
            assessments.submit_response(db, assessment.id, answer["question_id"], answer["answer_id"], answer["confidence"], answer["response_time_ms"])
        assessments.complete_assessment(db, assessment.id)
        finances.replace_finances(db, user.id, income="120000", expenses="65000", liquid="250000", liabilities=[])
        for name, kind, target, funded, years in [("Synthetic emergency reserve", "emergency", "390000", "250000", 1), ("Synthetic long-term retirement goal", "retirement", "30000000", "0", 30)]:
            goals.create_goal(db, user.id, {"name": name, "goal_type": kind, "target_amount": target, "current_funding": funded, "horizon_years": years, "priority": "high", "notes": "Invented demonstration goal. Funding is an earmark in existing assets, not extra wealth."})
        document = Document(user_id=user.id, kind="demo_portfolio", filename="SYNTHETIC-MF-EVIDENCE-DEMO.json", status="extracted", validation_status="valid", parser_version=SEED,
            metadata_json={"synthetic": True, "fixture_version": 3, "seed": SEED, "price_sources": [{"isin": row[0]["isin"], "source": row[3], "as_of": row[2]["date"]} for row in positions], "note": "Invented quantities in real MF schemes. No actual account, purchase cost or complete transaction history."},
            warning_json=["Synthetic holdings and cashflow assumptions. MF NAV/disclosure evidence is public and dated. Direct equity price below is an explicit fixture assumption."])
        db.add(document)
        db.flush()
        for resolved, units, latest, _ in positions:
            fund = Fund(user_id=user.id, document_id=document.id, amc=resolved.get("fund_house") or "Public scheme identity", folio="SYNTHETIC", scheme_name=resolved["scheme_name"], isin=resolved["isin"])
            db.add(fund)
            db.flush()
            quantity, nav = Decimal(units), Decimal(str(latest["value"]))
            db.add(Holding(user_id=user.id, document_id=document.id, fund_id=fund.id, closing_units=quantity, nav=nav, valuation=quantity*nav, valuation_date=latest["date"], asset_class="mutual_fund", source_page=1))
        direct = Fund(user_id=user.id, document_id=document.id, amc="EQUITY", folio="SYNTHETIC", scheme_name="HDFC Bank (synthetic quantity/reference price)", isin="INE040A01034")
        db.add(direct)
        db.flush()
        db.add(Holding(user_id=user.id, document_id=document.id, fund_id=direct.id, closing_units=Decimal(100), nav=Decimal(800), valuation=Decimal(80000), valuation_date=date.today().isoformat(), asset_class="equity", source_page=1))
        for field in ("finances_status", "goals_status", "portfolio_status"):
            journey.set_status(db, user.id, field, "provided")
        journey.set_step(db, user.id, "analysis")
        db.commit()
        return {"user_id": user.id, "name": NAME, "created": True, "synthetic": True, "funds": len(positions), "source_dates": [row[2]["date"] for row in positions]}


if __name__ == "__main__":
    print(json.dumps(create_demo()))
