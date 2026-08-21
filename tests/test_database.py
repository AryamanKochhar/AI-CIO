from decimal import Decimal
from database import holdings, replace_portfolio
from parser import FundHolding, ParseResult
def test_database_roundtrip(tmp_path):
    result=ParseResult([FundHolding("AMC","F1","Fund",None,Decimal("1"),Decimal("2"),Decimal("10"),Decimal("20"),None,2)],[],{2:"redacted"},[])
    con=replace_portfolio(tmp_path/"x.db",result)
    assert holdings(con)[0]["valuation"] == Decimal("20")
