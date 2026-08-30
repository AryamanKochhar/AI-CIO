"""CDSL CAS upload, idempotency, twin, and user isolation."""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import ROOT

FIXTURE = ROOT / "tests" / "fixtures" / "CDSL.pdf"
pytestmark = pytest.mark.integration


@pytest.mark.skipif(not FIXTURE.exists(), reason="CDSL.pdf fixture missing")
def test_upload_cdsl_cas_extracts_portfolio(client):
    user = client.post("/users", json={"name": "CDSL User"}).json()
    with FIXTURE.open("rb") as handle:
        response = client.post(
            f"/users/{user['id']}/documents?kind=cdsl_statement",
            files={"file": ("CDSL.pdf", handle, "application/pdf")},
        )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["kind"] == "cdsl_statement"
    assert body["parser_pending"] is False
    assert body["already_processed"] is False
    assert body["holdings"] >= 20
    assert body["transactions"] >= 10
    assert body["status"] in {"extracted", "needs_review"}
    assert body["statement_period"]["start"] == "01-05-2026"
    assert body["summary"]["portfolio_value"] == "1257065.12"

    holdings = client.get(f"/users/{user['id']}/holdings").json()
    assert len(holdings) == body["holdings"]
    assert any(h.get("asset_class") == "equity" for h in holdings)
    assert any(h.get("asset_class") == "mutual_fund" for h in holdings)

    twin = client.get(f"/users/{user['id']}/twin").json()
    assert twin["portfolio"]["holdings_count"] == body["holdings"]
    assert twin["portfolio"]["provenance"]["source"] == "CDSL CAS"
    assert twin["portfolio"]["provenance"]["period_start"] == "01-05-2026"


@pytest.mark.skipif(not FIXTURE.exists(), reason="CDSL.pdf fixture missing")
def test_cdsl_duplicate_upload_is_idempotent(client):
    user = client.post("/users", json={"name": "CDSL Dup"}).json()
    for _ in range(2):
        with FIXTURE.open("rb") as handle:
            response = client.post(
                f"/users/{user['id']}/documents?kind=cdsl_statement",
                files={"file": ("CDSL.pdf", handle, "application/pdf")},
            )
        assert response.status_code == 200, response.text
    body = response.json()
    assert body["already_processed"] is True
    assert "already been processed" in body["warnings"][0].lower()

    docs = client.get(f"/users/{user['id']}/documents").json()
    cdsl_docs = [d for d in docs if d["kind"] == "cdsl_statement"]
    assert len(cdsl_docs) == 1

    holdings = client.get(f"/users/{user['id']}/holdings").json()
    assert len(holdings) == body["holdings"]


@pytest.mark.skipif(not FIXTURE.exists(), reason="CDSL.pdf fixture missing")
def test_cdsl_rejects_non_cdsl_pdf(client):
    user = client.post("/users", json={"name": "Bad CDSL"}).json()
    payload = b"%PDF-1.4\n% not a cdsl statement - missing Central Depository markers\n" * 3
    response = client.post(
        f"/users/{user['id']}/documents?kind=cdsl_statement",
        files={"file": ("fake.pdf", payload, "application/pdf")},
    )
    assert response.status_code == 400
    assert "CDSL" in response.json()["detail"]


@pytest.mark.skipif(not FIXTURE.exists(), reason="CDSL.pdf fixture missing")
def test_cdsl_user_isolation(client):
    alice = client.post("/users", json={"name": "Alice CDSL"}).json()
    bob = client.post("/users", json={"name": "Bob CDSL"}).json()
    with FIXTURE.open("rb") as handle:
        client.post(
            f"/users/{alice['id']}/documents?kind=cdsl_statement",
            files={"file": ("CDSL.pdf", handle, "application/pdf")},
        )
    bob_docs = client.get(f"/users/{bob['id']}/documents").json()
    bob_holdings = client.get(f"/users/{bob['id']}/holdings").json()
    assert bob_docs == []
    assert bob_holdings == []


def test_upload_nsdl_statement_still_pending(client):
    user = client.post("/users", json={"name": "NSDL Still"}).json()
    payload = b"%PDF-1.4\n% synthetic NSDL statement\n"
    response = client.post(
        f"/users/{user['id']}/documents?kind=nsdl_statement",
        files={"file": ("nsdl.pdf", payload, "application/pdf")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["parser_pending"] is True
    assert body["holdings"] == 0
