"""User-scoped evidence import, cache revision and HTTP behavior."""
from datetime import date

from ai_cio.services import identity
from ai_cio.services.decision_cache import compute_input_fingerprint
from domain.decision.contracts import DecisionRequest


def disclosure():
    return {"scheme_code":122639,"scheme_isin":"INF879O01027","source_url":"https://amc.ppfas.com/disclosures/test-evidence.xlsx","observed_on":date.today().isoformat(),"holdings":[{"isin":"INE040A01034","name":"HDFC Bank","weight_pct":10,"asset_class":"equity"}],"benchmark_id":"NIFTY_500_TRI","benchmark_name":"Nifty 500 TRI"}


def test_unknown_user_cannot_read_or_write_mf_evidence(client,tmp_path,monkeypatch):
    monkeypatch.setenv("MUTUAL_FUND_CACHE_DIR",str(tmp_path))
    assert client.get("/users/999999/mutual-funds").status_code == 404
    assert client.post("/users/999999/mutual-funds/disclosures",json=disclosure()).status_code == 404
    assert not list(tmp_path.rglob("*.json"))


def test_import_is_scoped_and_invalidates_only_owners_decision(client,db,tmp_path,monkeypatch):
    monkeypatch.setenv("MUTUAL_FUND_CACHE_DIR",str(tmp_path))
    owner=identity.create_user(db,"Synthetic MF owner")
    other=identity.create_user(db,"Synthetic MF other")
    db.commit()
    request=DecisionRequest.from_payload(user_id=owner.id,objective="review_mutual_fund_portfolio")
    other_request=DecisionRequest.from_payload(user_id=other.id,objective="review_mutual_fund_portfolio")
    before=compute_input_fingerprint(db,owner.id,request)
    other_before=compute_input_fingerprint(db,other.id,other_request)
    result=client.post(f"/users/{owner.id}/mutual-funds/disclosures",json=disclosure())
    assert result.status_code == 200,result.text
    assert result.headers["cache-control"] == "private, no-store"
    assert result.json()["provenance"] == "user_supplied_source_document"
    assert result.json()["coverage_pct"] == 10
    assert compute_input_fingerprint(db,owner.id,request) != before
    assert compute_input_fingerprint(db,other.id,other_request) == other_before


def test_import_rejects_wrong_domain_and_price_index_without_writing(client,db,tmp_path,monkeypatch):
    monkeypatch.setenv("MUTUAL_FUND_CACHE_DIR",str(tmp_path))
    owner=identity.create_user(db,"Synthetic MF bad import")
    db.commit()
    bad={**disclosure(),"source_url":"https://attacker.example/portfolio.xlsx"}
    assert client.post(f"/users/{owner.id}/mutual-funds/disclosures",json=bad).status_code == 422
    bad={"benchmark_id":"NIFTY_500","name":"Nifty 500 Price Index","kind":"price","source_url":"https://www.niftyindices.com/reports/historical-data","observed_on":date.today().isoformat(),"points":[{"date":"2025-01-01","value":100},{"date":"2026-01-01","value":110}]}
    assert client.post(f"/users/{owner.id}/mutual-funds/benchmarks",json=bad).status_code == 422
    assert not list(tmp_path.rglob("*.json"))


def test_empty_portfolio_reports_missing_funds_without_invented_returns(client,db,tmp_path,monkeypatch):
    monkeypatch.setenv("MUTUAL_FUND_CACHE_DIR",str(tmp_path))
    owner=identity.create_user(db,"Synthetic MF no records")
    db.commit()
    result=client.get(f"/users/{owner.id}/mutual-funds")
    assert result.status_code == 200,result.text
    data=result.json()
    assert data["available"] is False
    assert data["funds"] == []
    assert data["overlaps"] == []
    assert data["correlations"] == []
    assert result.headers["cache-control"] == "private, no-store"
