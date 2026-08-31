#!/usr/bin/env python3
"""Probe which LiteLLM gateway models accept a minimal completion request."""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

MODELS = (
    "kimi",
    "kimi-k3",
    "kimi-code",
    "kimi-k2.7-code",
    "kimi-k2.7-code-highspeed",
    "kimi-k2.6",
)

SECRET_PATTERNS = (
    re.compile(r"(?i)(authorization\s*[:=]\s*)(?:bearer\s+)?[\w\-\.~+/=]{8,}"),
    re.compile(r"(?i)(api[_-]?key\s*[:=]\s*)[\w\-\.~+/=]{8,}"),
    re.compile(r"(?i)(bearer\s+)[\w\-\.~+/=]{8,}"),
    re.compile(r"sk-[a-zA-Z0-9]{8,}"),
    re.compile(r"ak-[a-zA-Z0-9]{8,}"),
)


def _env(name: str, *aliases: str) -> str:
    import os

    for key in (name, *aliases):
        value = os.getenv(key, "").strip()
        if value:
            return value
    return ""


def _sanitize(text: str, api_key: str) -> str:
    out = text
    if api_key and len(api_key) >= 4:
        out = out.replace(api_key, "[REDACTED]")
    for pattern in SECRET_PATTERNS:
        out = pattern.sub("[REDACTED]", out)
    return out[:300]


def _short_error(body: str) -> str:
    try:
        data = json.loads(body)
        err = data.get("error") or {}
        msg = err.get("message") or body
    except json.JSONDecodeError:
        msg = body
    msg = " ".join(str(msg).split())
    if len(msg) > 180:
        msg = msg[:177] + "..."
    return msg


def test_model(*, client: httpx.Client, base_url: str, api_key: str, model: str) -> dict:
    url = f"{base_url.rstrip('/')}/v1/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
        "max_tokens": 8,
        "temperature": 0,
    }
    started = time.perf_counter()
    try:
        response = client.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        latency_ms = int((time.perf_counter() - started) * 1000)
        if response.status_code == 200:
            try:
                data = response.json()
                text = (
                    ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
                ).strip()
            except (json.JSONDecodeError, IndexError, AttributeError):
                text = ""
            return {
                "model": model,
                "works": bool(text),
                "status": response.status_code,
                "latency_ms": latency_ms,
                "response": text or "(empty)",
                "error": "",
            }
        return {
            "model": model,
            "works": False,
            "status": response.status_code,
            "latency_ms": latency_ms,
            "response": "",
            "error": _sanitize(_short_error(response.text), api_key),
        }
    except Exception as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        return {
            "model": model,
            "works": False,
            "status": None,
            "latency_ms": latency_ms,
            "response": "",
            "error": _sanitize(str(exc), api_key),
        }


def main() -> int:
    base_url = _env("LITELLM_BASE_URL", "LLM_BASE_URL")
    api_key = _env("LITELLM_API_KEY", "LLM_API_KEY")

    print("=" * 50)
    print("LITELLM MODEL AVAILABILITY TEST")
    print("=" * 50)
    print()

    if not base_url or not api_key:
        print("Missing LITELLM_BASE_URL or LITELLM_API_KEY in .env")
        return 1

    results: list[dict] = []
    with httpx.Client(timeout=60.0) as client:
        for model in MODELS:
            print(f"Testing {model} ...", flush=True)
            result = test_model(client=client, base_url=base_url, api_key=api_key, model=model)
            results.append(result)

    print()
    print("Results")
    print("-" * 50)
    working = []
    for r in results:
        status = r["status"] if r["status"] is not None else "ERR"
        flag = "YES" if r["works"] else "NO"
        print(f"{r['model']:28} works={flag:3}  status={status}  {r['latency_ms']}ms")
        if r["works"]:
            working.append(r["model"])
            print(f"{'':28} response: {r['response']}")
        elif r["error"]:
            print(f"{'':28} error: {r['error']}")

    print()
    print("-" * 50)
    if working:
        print(f"Working models ({len(working)}): {', '.join(working)}")
    else:
        print("Working models: none")
    print("=" * 50)

    return 0 if working else 1


if __name__ == "__main__":
    sys.exit(main())
