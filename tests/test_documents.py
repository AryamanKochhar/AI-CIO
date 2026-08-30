"""Unified document ingestion: CAS parsing and NSDL/CDSL registration."""
from __future__ import annotations

import pytest

from tests.conftest import ROOT, _synthetic_result

pytestmark = pytest.mark.integration


def test_upload_cas_through_unified_endpoint(client):
    pdf_path = ROOT / "data" / "cas.pdf"
    if not pdf_path.exists():
        pytest.skip("No local CAS PDF in data/")
    user = client.post("/users", json={"name": "Docs"}).json()
    with pdf_path.open("rb") as handle:
        response = client.post(
            f"/users/{user['id']}/documents?kind=cas_pdf",
            files={"file": (pdf_path.name, handle, "application/pdf")},
        )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["kind"] == "cas_pdf"
    assert body["holdings"] >= 1
    assert body["parser_pending"] is False
    assert body["status"] in {"extracted", "needs_review"}

    docs = client.get(f"/users/{user['id']}/documents").json()
    assert len(docs) == 1
    assert docs[0]["kind"] == "cas_pdf"
    assert docs[0]["status"] in {"extracted", "needs_review"}


def test_upload_nsdl_statement_registers_pending_document(client):
    user = client.post("/users", json={"name": "NSDL"}).json()
    payload = b"%PDF-1.4\n% synthetic NSDL statement\n"
    response = client.post(
        f"/users/{user['id']}/documents?kind=nsdl_statement",
        files={"file": ("nsdl.pdf", payload, "application/pdf")},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["kind"] == "nsdl_statement"
    assert body["holdings"] == 0
    assert body["parser_pending"] is True
    assert "pending" in body["status"]

    docs = client.get(f"/users/{user['id']}/documents").json()
    assert len(docs) == 1
    assert docs[0]["kind"] == "nsdl_statement"
    assert docs[0]["status"] == "pending"
    assert docs[0]["validation_status"] == "unvalidated"


def test_upload_cdsl_statement_requires_valid_cdsl_pdf(client):
    user = client.post("/users", json={"name": "CDSL"}).json()
    payload = b"%PDF-1.4\n% synthetic CDSL statement\n"
    response = client.post(
        f"/users/{user['id']}/documents?kind=cdsl_statement",
        files={"file": ("cdsl.pdf", payload, "application/pdf")},
    )
    assert response.status_code == 400
    assert "CDSL" in response.json()["detail"]


def test_document_upload_rejects_unsupported_kind(client):
    user = client.post("/users", json={"name": "Bad"}).json()
    response = client.post(
        f"/users/{user['id']}/documents?kind=not_a_kind",
        files={"file": ("x.pdf", b"%PDF", "application/pdf")},
    )
    assert response.status_code == 400
    assert "Unsupported" in response.json()["detail"]


def test_documents_are_user_scoped(client):
    alice = client.post("/users", json={"name": "Alice"}).json()
    bob = client.post("/users", json={"name": "Bob"}).json()
    client.post(
        f"/users/{alice['id']}/documents?kind=nsdl_statement",
        files={"file": ("a.pdf", b"%PDF", "application/pdf")},
    )
    alice_docs = client.get(f"/users/{alice['id']}/documents").json()
    bob_docs = client.get(f"/users/{bob['id']}/documents").json()
    assert len(alice_docs) == 1
    assert len(bob_docs) == 0


def test_cas_service_ingest_sets_document_status(db):
    from ai_cio.services.identity import create_user
    from ai_cio.services.portfolio import ingest_cas

    pdf_path = ROOT / "data" / "cas.pdf"
    if not pdf_path.exists():
        pytest.skip("No local CAS PDF in data/")
    user = create_user(db, "ServiceIngest")
    document, result = ingest_cas(db, user.id, pdf_path)
    db.commit()
    assert document.status == "pending"  # portfolio.ingest_cas does not set status; documents svc does
    assert document.validation_status is None
