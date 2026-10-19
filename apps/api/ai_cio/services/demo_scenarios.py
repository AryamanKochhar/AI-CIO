"""Invented persona finances and positions in real, verified NSE instruments.

Prices here are explicit fixture assumptions, never represented as market quotes.
An available fresh Dhan daily close replaces only the demo valuation, not its lots.
"""
from datetime import date, timedelta
from decimal import Decimal

from ai_cio.db.models import Document, FixedDeposit, Fund, Holding, Security, Transaction
from ai_cio.services import finances, goals
from ai_cio.services.holding_market_data import cached_history, instrument_catalogue

SCENARIOS = {
    "tom": {
        "household": "Two incomes, no dependants; retirement in four years",
        "positions": [("HDFCBANK", 2000, "900"), ("RELIANCE", 800, "1500"), ("ITC", 2000, "450"), ("TCS", 250, "3500"), ("ICICIBANK", 1000, "1400")],
        "debt_buckets": [("Short-duration debt allocation (demo)", "4500000"), ("Liquid fund allocation (demo)", "1325000")],
        "liabilities": [], "fds": [("State Bank of India", "1000000", "6.75"), ("HDFC Bank", "750000", "6.50")],
        "extra_goals": [("Retirement medical reserve", "emergency", "3000000", "800000", 4), ("Travel after retirement", "travel", "1200000", "250000", 5)],
    },
    "maya": {
        "household": "Early-career professional; education-loan EMI included in expenses",
        "positions": [("INFY", 80, "1700"), ("HDFCBANK", 80, "900"), ("RELIANCE", 40, "1500")],
        "debt_buckets": [("Short-duration debt allocation (demo)", "82000")],
        "liabilities": [{"name": "Education loan (demo)", "balance": "450000", "monthly_payment": "9000"}],
        "fds": [("ICICI Bank", "50000", "6.25")],
        "extra_goals": [("Six months of expenses", "emergency", "390000", "250000", 1), ("Long-term retirement savings", "retirement", "40000000", "0", 30)],
    },
    "arjun": {
        "household": "One income and two children; home-loan EMI included in expenses",
        "positions": [("HDFCBANK", 500, "900"), ("ICICIBANK", 300, "1400"), ("ITC", 600, "450"), ("LT", 60, "3500")],
        "debt_buckets": [("Education debt allocation (demo)", "450000")],
        "liabilities": [{"name": "Home loan (demo)", "balance": "2800000", "monthly_payment": "35000"}],
        "fds": [("State Bank of India", "300000", "6.75"), ("ICICI Bank", "200000", "6.50")],
        "extra_goals": [("Family emergency reserve", "emergency", "720000", "500000", 1), ("Retirement at age 60", "retirement", "30000000", "0", 18)],
    },
}


def populate_financial_scenario(db, user_id: int, persona: dict) -> None:
    scenario = SCENARIOS[persona["id"]]
    finances.replace_finances(db, user_id, income=persona["income"], expenses=persona["expenses"],
                              liquid=persona["liquid"], liabilities=scenario["liabilities"])
    specifications = [(persona["goal"], persona["goal_type"], persona["target"], persona["funding"], persona["horizon"]), *scenario["extra_goals"]]
    for index, (name, kind, target, funding, horizon) in enumerate(specifications):
        goals.create_goal(db, user_id, {"name": name, "goal_type": kind, "target_amount": target,
            "current_funding": funding, "horizon_years": horizon, "priority": "high" if index < 2 else "medium",
            "notes": "Synthetic demo assumption. Goal funding is an earmark within existing assets, not an extra asset; EMI is included in expenses."})
    today = date.today()
    for bank, principal, rate in scenario["fds"]:
        db.add(FixedDeposit(user_id=user_id, bank_name=bank, account_label="Synthetic demo deposit",
            principal=Decimal(principal), interest_rate_pa=Decimal(rate), tenure_months=24,
            start_date=(today - timedelta(days=365)).isoformat(), maturity_date=(today + timedelta(days=365)).isoformat(),
            compounding="quarterly", is_senior_citizen=False,
            notes="Invented demo principal and contracted rate; not a current bank offer or broker account balance."))
    document = Document(user_id=user_id, kind="demo_portfolio", filename="SYNTHETIC-DEMO-portfolio.json",
        status="extracted", validation_status="valid", parser_version="demo-fixture-2",
        metadata_json={"synthetic": True, "persona": persona["id"], "fixture_version": 2, "price_sources": [],
                       "persona_context": {"age": persona["age"], "occupation": persona["occupation"], "household": scenario["household"]}},
        warning_json=["Quantities, purchase costs, FDs and cashflows are invented. Fresh Dhan closes, when available, value demo equity only. Reference values are used offline and are not market quotes."])
    db.add(document)
    db.flush()
    instruments = {item["symbol"]: item for item in instrument_catalogue()}
    price_sources = []
    for index, (symbol, quantity, assumed_price) in enumerate(scenario["positions"]):
        item = instruments[symbol]
        history = cached_history("NSE_EQ", item["security_id"])
        price = Decimal(str(history["close"][-1])) if history else Decimal(assumed_price)
        price_date = history["as_of"] if history else "2026-10-01"
        price_sources.append({"symbol": symbol, "source": "Dhan completed daily close" if history else "Synthetic reference assumption", "as_of": price_date})
        if not db.query(Security).filter(Security.isin == item["isin"]).first():
            db.add(Security(isin=item["isin"], symbol=symbol, name=item["name"], exchange="NSE", asset_class="equity",
                sector_index_code=item["sector_index_code"], sector_name=item["sector"], classification_source="Verified demo instrument mapping"))
        fund = Fund(user_id=user_id, document_id=document.id, amc="EQUITY", folio="DEMO", scheme_name=item["name"], isin=item["isin"])
        db.add(fund)
        db.flush()
        recent = max(1, quantity // 3)
        sold = max(1, quantity // 10) if index == 0 else 0
        old = quantity - recent
        old_price = (Decimal(assumed_price) * Decimal("0.83")).quantize(Decimal("0.01"))
        new_price = (Decimal(assumed_price) * Decimal("1.08")).quantize(Decimal("0.01"))
        cost = old * old_price + recent * new_price
        value = price * quantity
        db.add(Holding(user_id=user_id, document_id=document.id, fund_id=fund.id,
            opening_units=old + sold, closing_units=quantity, nav=price, valuation=value,
            valuation_date=price_date, asset_class="equity", invested_amount=cost,
            unrealised_pl=value-cost, unrealised_pl_pct=((value/cost)-1)*100, source_page=1))
        lot_rows = [(today-timedelta(days=730), "BUY", old+sold, old_price), (today-timedelta(days=120), "BUY", recent, new_price)]
        if sold:
            lot_rows.append((today-timedelta(days=30), "SELL", sold, Decimal(assumed_price)*Decimal("1.04")))
        for day, kind, units, lot_price in lot_rows:
            db.add(Transaction(user_id=user_id, document_id=document.id, fund_id=fund.id, date=day.isoformat(),
                transaction_type=kind, description=f"Synthetic demo {kind.lower()}; invented adjusted quantity/cost for tax-lot demonstration",
                amount=lot_price*units, units=units, nav=lot_price, source_page=1))
    for name, amount in scenario["debt_buckets"]:
        fund = Fund(user_id=user_id, document_id=document.id, amc="SYNTHETIC EXAMPLE", folio="DEMO", scheme_name=name)
        db.add(fund)
        db.flush()
        db.add(Holding(user_id=user_id, document_id=document.id, fund_id=fund.id, closing_units=Decimal(amount)/100,
            nav=Decimal("100"), valuation=Decimal(amount), invested_amount=Decimal(amount),
            valuation_date="2026-10-01", asset_class="debt", source_page=1))
    document.metadata_json = {**document.metadata_json, "price_sources": price_sources}
    db.flush()
