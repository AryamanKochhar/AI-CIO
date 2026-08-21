from parser import parse_page_text, normalize_transaction
def test_normalization_keeps_failures_out_of_purchases():
    assert normalize_transaction("Payment not received from banker") == "FAILED_PAYMENT"
    assert normalize_transaction("Purchase - Systematic-Normal") == "SIP_PURCHASE"
def test_parser_extracts_a_holding_and_transaction():
    text="""AMC: Example AMC\nFolio No: 1234\nScheme: Example Fund\nISIN: INF000000001\nOpening Units: 10.0\nClosing Units: 12.0\nNAV: 100.00\nValuation: 1200.00\n01/01/2026 Purchase - Systematic-Normal 200.00 2.0000 100.0000 12.0000"""
    hs, tx = parse_page_text(text, 3, "Example AMC")
    assert len(hs)==1 and hs[0].valuation == 1200
    assert tx[0].transaction_type == "SIP_PURCHASE"
