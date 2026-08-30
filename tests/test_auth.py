"""MVP authentication tests. Passwords are hashed, never stored plaintext."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


def test_register_creates_user_with_password_hash(client):
    response = client.post("/auth/register", json={"name": "Ada", "email": "ada@example.com", "password": "secure123"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["name"] == "Ada"
    assert body["email"] == "ada@example.com"
    assert "password_hash" not in body


def test_login_returns_user_for_valid_credentials(client):
    client.post("/auth/register", json={"name": "Bob", "email": "bob@example.com", "password": "secure123"})
    response = client.post("/auth/login", json={"email": "bob@example.com", "password": "secure123"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["email"] == "bob@example.com"
    assert body["name"] == "Bob"


def test_login_rejects_bad_password(client):
    client.post("/auth/register", json={"name": "Carol", "email": "carol@example.com", "password": "secure123"})
    response = client.post("/auth/login", json={"email": "carol@example.com", "password": "wrong"})
    assert response.status_code == 400
    assert "Invalid" in response.json()["detail"]


def test_register_rejects_duplicate_email(client):
    client.post("/auth/register", json={"name": "Dan", "email": "dan@example.com", "password": "secure123"})
    response = client.post("/auth/register", json={"name": "Dan2", "email": "dan@example.com", "password": "secure123"})
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_password_is_not_stored_plaintext(client, db):
    from ai_cio.db.models import User

    client.post("/auth/register", json={"name": "Eve", "email": "eve@example.com", "password": "secure123"})
    user = db.query(User).filter(User.email == "eve@example.com").first()
    assert user is not None
    assert user.password_hash is not None
    assert user.password_hash != "secure123"
    assert "pbkdf2_sha256" in user.password_hash


def test_register_rejects_short_password(client):
    response = client.post("/auth/register", json={"name": "Fail", "email": "fail@example.com", "password": "short"})
    assert response.status_code == 400
    assert "8" in response.json()["detail"]
