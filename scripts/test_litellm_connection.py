#!/usr/bin/env python3
"""Standalone LiteLLM gateway diagnostic.

Tests the external LiteLLM service directly — no AI-CIO application imports.
Mirrors endpoints used by apps/api/ai_cio/llm/provider.py (LiteLLMProvider):
  - GET  {LITELLM_BASE_URL}/v1/models
  - POST {LITELLM_BASE_URL}/v1/chat/completions
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

# Endpoints aligned with LiteLLMProvider in ai_cio/llm/provider.py
MODELS_PATH = "/v1/models"
CHAT_COMPLETIONS_PATH = "/v1/chat/completions"

SECRET_PATTERNS = (
  re.compile(r"(?i)(authorization\s*[:=]\s*)(bearer\s+)?[\w\-\.~+/=]{8,}"),
  re.compile(r"(?i)(api[_-]?key\s*[:=]\s*)[\w\-\.~+/=]{8,}"),
  re.compile(r"(?i)(bearer\s+)[\w\-\.~+/=]{8,}"),
  re.compile(r"(?i)(x-api-key\s*[:=]\s*)[\w\-\.~+/=]{8,}"),
  re.compile(r"(?i)(token\s*[:=]\s*)[\w\-\.~+/=]{8,}"),
  re.compile(r"sk-[a-zA-Z0-9]{8,}"),
  re.compile(r"ak-[a-zA-Z0-9]{8,}"),
  re.compile(r"org-[a-f0-9]{8,}"),
)


def _env(name: str, *aliases: str) -> str:
    import os

    for key in (name, *aliases):
        value = os.getenv(key, "").strip()
        if value:
            return value
    return ""


def _sanitize(text: str, secrets: list[str]) -> str:
    out = text
    for secret in secrets:
        if secret and len(secret) >= 4:
            out = out.replace(secret, "[REDACTED]")
    for pattern in SECRET_PATTERNS:
        out = pattern.sub("[REDACTED]", out)
    return out


def _classify_error(
    *,
    exc: Exception | None = None,
    status_code: int | None = None,
    body: str = "",
    reachable: bool = False,
    model_available: bool = False,
) -> str:
    if exc is not None:
        name = type(exc).__name__
        msg = str(exc).lower()
        if isinstance(exc, httpx.ConnectTimeout) or isinstance(exc, httpx.ReadTimeout):
            return "CONNECTION_TIMEOUT"
        if isinstance(exc, httpx.ConnectError):
            if "name or service not known" in msg or "nodename nor servname" in msg:
                return "DNS_ERROR"
            if "certificate" in msg or "ssl" in msg or "tls" in msg:
                return "TLS_ERROR"
            return "NETWORK_ERROR"
        if name in {"ConnectError", "NetworkError"}:
            return "NETWORK_ERROR"
        return "UNKNOWN"

    if status_code == 401:
        return "HTTP_401_UNAUTHORIZED"
    if status_code == 403:
        return "HTTP_403_FORBIDDEN"
    if status_code == 404:
        return "HTTP_404_ENDPOINT_NOT_FOUND"
    if status_code == 429:
        return "HTTP_429_RATE_LIMITED"
    if status_code == 400:
        lowered = body.lower()
        if "model" in lowered and ("not found" in lowered or "does not exist" in lowered or "invalid" in lowered):
            return "MODEL_NOT_FOUND"
        return "HTTP_400_BAD_REQUEST"
    if status_code is not None and status_code >= 500:
        return "SERVER_ERROR"
    if reachable and not model_available:
        return "MODEL_NOT_FOUND"
    return "UNKNOWN"


def _parse_upstream_hint(body: str) -> str | None:
    lowered = body.lower()
    if "insufficient balance" in lowered or "recharge your account" in lowered:
        return "upstream_billing"
    if "suspended" in lowered and "account" in lowered:
        return "upstream_account_suspended"
    if "no deployments available" in lowered or "cooldown_list" in lowered:
        return "no_deployments"
    if "rate limit" in lowered or "too many requests" in lowered:
        return "rate_limit"
    return None


def _failure_details(code: str, upstream_hint: str | None = None) -> tuple[str, str, str]:
    if code == "HTTP_429_RATE_LIMITED" and upstream_hint == "upstream_billing":
        return (
            "The gateway accepted the request but the upstream model provider rejected it.",
            "Moonshot (kimi) account is suspended due to insufficient balance.",
            "Recharge the Moonshot provider account or switch LLM_MODEL to a funded provider.",
        )
    if code == "HTTP_429_RATE_LIMITED" and upstream_hint == "upstream_account_suspended":
        return (
            "The gateway accepted the request but the upstream model provider rejected it.",
            "The upstream provider account is suspended.",
            "Restore the upstream provider account or choose a different LLM_MODEL.",
        )
    if code == "HTTP_429_RATE_LIMITED" and upstream_hint == "no_deployments":
        return (
            "The gateway accepted the request but no healthy deployment exists for the model.",
            "All kimi deployments are in cooldown after upstream failures (often billing or provider outage).",
            "Recharge/fix the upstream Moonshot account, wait for cooldown, or switch LLM_MODEL.",
        )
    mapping: dict[str, tuple[str, str, str]] = {
        "NETWORK_ERROR": (
            "Could not establish a TCP connection to the LiteLLM gateway.",
            "The host may be down, firewalled, or unreachable from this network.",
            "Verify VPN/network access and that https://litellm-infra.valura.ai is reachable.",
        ),
        "DNS_ERROR": (
            "DNS resolution for the LiteLLM host failed.",
            "The hostname could not be resolved from this machine.",
            "Check DNS, VPN, and that LITELLM_BASE_URL is correct.",
        ),
        "TLS_ERROR": (
            "TLS handshake with the LiteLLM gateway failed.",
            "Certificate or SSL/TLS configuration may be invalid or intercepted.",
            "Verify TLS trust chain and LITELLM_BASE_URL scheme (https).",
        ),
        "CONNECTION_TIMEOUT": (
            "The request to the LiteLLM gateway timed out.",
            "The server may be overloaded or blocked by network policy.",
            "Retry later; check firewall/VPN; confirm gateway health with infra team.",
        ),
        "HTTP_401_UNAUTHORIZED": (
            "The gateway is reachable but rejected the supplied credentials.",
            "Invalid, expired, or revoked LITELLM_API_KEY.",
            "Verify or rotate the LiteLLM virtual key in .env (LITELLM_API_KEY).",
        ),
        "HTTP_403_FORBIDDEN": (
            "Authentication succeeded partially but access was forbidden.",
            "The key may lack permission for the requested model or endpoint.",
            "Confirm key scopes with LiteLLM admin; verify model access policy.",
        ),
        "HTTP_404_ENDPOINT_NOT_FOUND": (
            "The requested LiteLLM endpoint was not found.",
            "LITELLM_BASE_URL may be wrong or the gateway path changed.",
            "Confirm base URL and that /v1/models and /v1/chat/completions exist.",
        ),
        "HTTP_429_RATE_LIMITED": (
            "The LiteLLM gateway rate-limited the request.",
            "Too many requests for this API key or tenant.",
            "Wait and retry; request higher quota if needed.",
        ),
        "HTTP_400_BAD_REQUEST": (
            "The gateway rejected the request payload.",
            "Malformed body, unsupported parameters, or invalid model identifier.",
            "Verify LLM_MODEL matches an id from GET /v1/models.",
        ),
        "MODEL_NOT_FOUND": (
            "The configured model is not available on the gateway.",
            "LLM_MODEL does not match any model id returned by /v1/models.",
            "Set LLM_MODEL to a valid id from the gateway model list.",
        ),
        "SERVER_ERROR": (
            "The LiteLLM gateway returned a server error.",
            "Upstream provider or LiteLLM proxy may be failing.",
            "Check LiteLLM infra logs/status; retry later.",
        ),
        "INVALID_RESPONSE": (
            "A response was received but could not be parsed or was empty.",
            "Unexpected response shape from the gateway.",
            "Inspect gateway logs; confirm OpenAI-compatible response format.",
        ),
        "UNKNOWN": (
            "The failure could not be classified confidently.",
            "See HTTP status and sanitized error body above.",
            "Review configuration and gateway documentation.",
        ),
    }
    return mapping.get(code, mapping["UNKNOWN"])


def _auth_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def _extract_model_ids(payload: Any) -> set[str]:
    ids: set[str] = set()
    if not isinstance(payload, dict):
        return ids
    data = payload.get("data")
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and item.get("id"):
                ids.add(str(item["id"]))
    models = payload.get("models")
    if isinstance(models, list):
        for item in models:
            if isinstance(item, str):
                ids.add(item)
            elif isinstance(item, dict) and item.get("id"):
                ids.add(str(item["id"]))
    return ids


def main() -> int:
    base_url = _env("LITELLM_BASE_URL", "LLM_BASE_URL").rstrip("/")
    api_key = _env("LITELLM_API_KEY", "LLM_API_KEY")
    model = _env("LLM_MODEL")
    secrets = [s for s in (api_key,) if s]

    print("=" * 40)
    print("AI-CIO LITELLM CONNECTION TEST")
    print("=" * 40)
    print()
    print("Configuration")
    print("-" * 40)
    print(f"Base URL: {'configured' if base_url else 'missing'}")
    print(f"API Key: {'configured' if api_key else 'missing'}")
    if model:
        print(f"Model: {model}")
    else:
        print("Model: (not set)")
    print()
    print("Provider endpoints (from LiteLLMProvider)")
    print("-" * 40)
    print(f"Health / models: GET {{base}}{MODELS_PATH}")
    print(f"Completion:      POST {{base}}{CHAT_COMPLETIONS_PATH}")
    print()

    if not base_url:
        print("=" * 40)
        print("RESULT: LITELLM CONNECTION FAILED")
        print("=" * 40)
        print()
        print("Failure:")
        print("LITELLM_BASE_URL is not set")
        print()
        print("Action:")
        print("Set LITELLM_BASE_URL in .env (e.g. https://litellm-infra.valura.ai).")
        return 1

    models_url = f"{base_url}{MODELS_PATH}"
    chat_url = f"{base_url}{CHAT_COMPLETIONS_PATH}"

    reachable = False
    connectivity_status: int | None = None
    latency_ms: int | None = None
    connectivity_exc: Exception | None = None
    models_payload: dict[str, Any] | None = None
    model_ids: set[str] = set()

    # TEST 1 — BASIC CONNECTIVITY
    print("Connectivity")
    print("-" * 40)
    started = time.perf_counter()
    try:
        headers = _auth_headers(api_key) if api_key else {}
        with httpx.Client(timeout=15.0) as client:
            response = client.get(models_url, headers=headers)
        latency_ms = int((time.perf_counter() - started) * 1000)
        connectivity_status = response.status_code
        reachable = connectivity_status < 500
        print(f"Gateway reachable: {'YES' if reachable else 'NO'}")
        print(f"HTTP status: {connectivity_status}")
        print(f"Latency: {latency_ms} ms")
        if response.status_code == 200:
            try:
                models_payload = response.json()
                model_ids = _extract_model_ids(models_payload)
            except json.JSONDecodeError:
                pass
    except Exception as exc:
        connectivity_exc = exc
        latency_ms = int((time.perf_counter() - started) * 1000)
        print("Gateway reachable: NO")
        print("HTTP status: (none)")
        print(f"Latency: {latency_ms} ms")
        safe_err = _sanitize(str(exc), secrets)
        print(f"error: {safe_err}")
    print()

    # TEST 2 — MODEL AVAILABILITY
    print("Model")
    print("-" * 40)
    if not model:
        print("MODEL CONFIGURATION:")
        print("missing")
        model_configured = False
        model_available = False
    else:
        model_configured = True
        model_available = model in model_ids if model_ids else False
        if models_payload is None and reachable and connectivity_status == 200:
            model_available = False
        print(f"Model configured: {'YES' if model_configured else 'NO'}")
        print(f"Model available: {'YES' if model_available else 'NO'}")
    print()

    # TEST 3 — AUTHENTICATION + minimal completion
    auth_success = False
    completion_success = False
    completion_status: int | None = None
    completion_body = ""
    completion_text = ""
    completion_exc: Exception | None = None
    response_received = False

    print("Authentication")
    print("-" * 40)
    if not api_key:
        print("API authentication: FAILED")
        print("model request: FAILED")
        print("HTTP status: (none)")
        print("response received: false")
        print("error: LITELLM_API_KEY is not set")
    elif not model:
        print("API authentication: FAILED")
        print("model request: FAILED")
        print("HTTP status: (none)")
        print("response received: false")
        print("error: LLM_MODEL is not set")
    else:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "Reply with exactly: LITELLM_OK"}],
            "max_tokens": 16,
            "temperature": 0,
        }
        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(chat_url, headers=_auth_headers(api_key), json=payload)
            completion_status = response.status_code
            response_received = True
            completion_body = response.text
            auth_success = response.status_code not in (401, 403)
            if response.status_code == 200:
                try:
                    data = response.json()
                    choices = data.get("choices") or []
                    if choices and isinstance(choices[0], dict):
                        message = choices[0].get("message") or {}
                        completion_text = str(message.get("content") or "").strip()
                    completion_success = bool(completion_text)
                    auth_success = True
                except json.JSONDecodeError:
                    completion_success = False
            print(f"API authentication: {'SUCCESS' if auth_success else 'FAILED'}")
            print(f"model request: {'SUCCESS' if completion_success else 'FAILED'}")
            print(f"HTTP status: {completion_status}")
            print(f"response received: {str(response_received).lower()}")
            if not auth_success or not completion_success:
                safe_body = _sanitize(completion_body[:2000], secrets)
                if safe_body.strip():
                    print(f"error body: {safe_body}")
        except Exception as exc:
            completion_exc = exc
            print("API authentication: FAILED")
            print("model request: FAILED")
            print("HTTP status: (none)")
            print("response received: false")
            print(f"error: {_sanitize(str(exc), secrets)}")
    print()

    print("Completion")
    print("-" * 40)
    if completion_success:
        print("Request: SUCCESS")
        print(f"Response: {completion_text}")
    else:
        print("Request: FAILED")
        if completion_text:
            print(f"Response: {completion_text}")
        elif completion_status is not None:
            print(f"HTTP status: {completion_status}")
    print()

    all_ok = (
        reachable
        and connectivity_status == 200
        and bool(api_key)
        and model_configured
        and (not model_configured or model_available or bool(model_ids))
        and auth_success
        and completion_success
    )

    # Strict pass: model must be available when we got a model list
    if model_configured and model_ids and not model_available:
        all_ok = False

    if all_ok:
        print("=" * 40)
        print("RESULT: LITELLM IS WORKING")
        print("=" * 40)
        return 0

    print("=" * 40)
    print("RESULT: LITELLM CONNECTION FAILED")
    print("=" * 40)
    print()

    upstream_hint = _parse_upstream_hint(completion_body)

    error_code = _classify_error(
        exc=connectivity_exc or completion_exc,
        status_code=completion_status or connectivity_status,
        body=completion_body,
        reachable=reachable,
        model_available=model_available if model_configured else False,
    )
    if completion_status == 429:
        error_code = "HTTP_429_RATE_LIMITED"
    if model_configured and model_ids and not model_available:
        error_code = "MODEL_NOT_FOUND"
    if not api_key and reachable:
        error_code = "HTTP_401_UNAUTHORIZED"
    if api_key and connectivity_status in (401, 403):
        error_code = "HTTP_401_UNAUTHORIZED" if connectivity_status == 401 else "HTTP_403_FORBIDDEN"

    failure_label = {
        "NETWORK_ERROR": "Network error",
        "DNS_ERROR": "DNS error",
        "TLS_ERROR": "TLS error",
        "CONNECTION_TIMEOUT": "Connection timeout",
        "HTTP_401_UNAUTHORIZED": "HTTP 401",
        "HTTP_403_FORBIDDEN": "HTTP 403",
        "HTTP_404_ENDPOINT_NOT_FOUND": "HTTP 404",
        "HTTP_429_RATE_LIMITED": "HTTP 429",
        "HTTP_400_BAD_REQUEST": "HTTP 400",
        "MODEL_NOT_FOUND": "Model not found",
        "SERVER_ERROR": f"HTTP {connectivity_status or completion_status or 500}",
        "INVALID_RESPONSE": "Invalid response",
        "UNKNOWN": "Unknown error",
    }.get(error_code, "Unknown error")

    what, why, action = _failure_details(error_code, upstream_hint)
    print("Failure:")
    print(failure_label)
    print()
    print("Meaning:")
    print(what)
    print()
    print("Likely cause:")
    print(why)
    print()
    print("Action:")
    print(action)
    print()
    print("Classification:")
    print(error_code)

    # TEST 4 — expanded diagnosis
    print()
    print("Diagnosis")
    print("-" * 40)
    print(f"WHAT FAILED: {what}")
    print(f"WHY IT LIKELY FAILED: {why}")
    print(f"WHAT NEEDS TO BE FIXED: {action}")

    return 1


if __name__ == "__main__":
    sys.exit(main())
