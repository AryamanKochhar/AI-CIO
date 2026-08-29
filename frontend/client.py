"""HTTP client for the unified AI-CIO UI. Talks only to FastAPI."""
from __future__ import annotations

import os
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
TIMEOUT = 8
CAS_TIMEOUT = 120


class ApiError(RuntimeError):
    pass


def _raise(response: requests.Response) -> None:
    try:
        detail = response.json().get("detail", response.text)
    except Exception:
        detail = response.text
    raise ApiError(str(detail))


def request(method: str, path: str, **kwargs):
    kwargs.setdefault("timeout", TIMEOUT)
    response = requests.request(method, f"{API_BASE_URL}{path}", **kwargs)
    if not response.ok:
        _raise(response)
    if response.content:
        return response.json()
    return None


def create_user(name: str) -> dict:
    return request("POST", "/users", json={"name": name})


def start_assessment(user_id: int) -> dict:
    return request("POST", "/assessments/start", json={"user_id": user_id})


def load_questions() -> dict:
    return request("GET", "/instruments/current/questions")


def submit_response(session_id: int, question_id: str, answer: str, confidence: int, response_time_ms: int) -> dict:
    return request(
        "POST",
        f"/assessments/{session_id}/responses",
        json={
            "question_id": question_id,
            "answer": answer,
            "confidence": confidence,
            "response_time_ms": response_time_ms,
        },
    )


def complete_assessment(session_id: int) -> dict:
    return request("POST", f"/assessments/{session_id}/complete")


def get_observations(session_id: int) -> dict:
    return request("GET", f"/assessments/{session_id}/observations")


def get_finances(user_id: int) -> dict:
    return request("GET", f"/users/{user_id}/finances") or {}


def put_finances(user_id: int, payload: dict) -> dict:
    return request("PUT", f"/users/{user_id}/finances", json=payload)


def skip_finances(user_id: int) -> dict:
    return request("PUT", f"/users/{user_id}/finances", json={"skipped": True})


def list_goals(user_id: int) -> list:
    return request("GET", f"/users/{user_id}/goals") or []


def add_goal(user_id: int, payload: dict) -> dict:
    return request("POST", f"/users/{user_id}/goals", json=payload)


def remove_goal(user_id: int, goal_id: int) -> dict:
    return request("DELETE", f"/users/{user_id}/goals/{goal_id}")


def skip_goals(user_id: int) -> dict:
    return request("POST", f"/users/{user_id}/goals/skip")


def upload_cas(user_id: int, name: str, data: bytes) -> dict:
    return request(
        "POST",
        f"/users/{user_id}/documents/cas",
        files={"file": (name, data, "application/pdf")},
        timeout=CAS_TIMEOUT,
    )


def skip_portfolio(user_id: int) -> dict:
    return request("PUT", f"/users/{user_id}/journey", json={"portfolio_status": "skipped"})


def get_holdings(user_id: int) -> list:
    return request("GET", f"/users/{user_id}/holdings") or []


def get_review(user_id: int) -> dict:
    return request("GET", f"/users/{user_id}/review")


def set_step(user_id: int, step: str) -> dict:
    return request("PUT", f"/users/{user_id}/journey", json={"current_step": step})


def record_decision(user_id: int, decision: str, notes: str | None = None) -> dict:
    return request("POST", f"/users/{user_id}/review-decision", json={"decision": decision, "notes": notes})
