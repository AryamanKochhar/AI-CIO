from decimal import Decimal
from domain.analysis import concentration_metrics, total_value, validate_valuation
def test_total_and_concentration():
    hs=[{"amc":"A","scheme_name":"one","valuation":Decimal("60")},{"amc":"B","scheme_name":"two","valuation":Decimal("25")},{"amc":"A","scheme_name":"three","valuation":Decimal("15")}]
    assert total_value(hs)==Decimal("100")
    assert concentration_metrics(hs)["top_3_percentage"]==Decimal("100")
    assert concentration_metrics(hs)["largest_amc_percentage"]==Decimal("75")

def test_valuation_validation_reports_difference():
    assert validate_valuation({"closing_units":Decimal("2"),"nav":Decimal("10"),"valuation":Decimal("20")})["status"] == "ok"
