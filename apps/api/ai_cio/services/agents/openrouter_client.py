"""Minimal OpenRouter chat client for decision agents."""
from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from ai_cio import settings

logger = logging.getLogger(__name__)


class OpenRouterError(RuntimeError):
    pass


def _message_text(message: dict[str, Any]) -> str | None:
    content = message.get("content")
    if isinstance(content, str) and content.strip():
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str) and item.strip():
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if isinstance(text, str) and text.strip():
                    parts.append(text)
        if parts:
            return "\n".join(parts)
    for key in ("reasoning", "reasoning_content"):
        value = message.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def chat_completion(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 8192,
    timeout: float = 180.0,
) -> str:
    api_key = settings.OPENROUTER_API_KEY
    if not api_key:
        raise OpenRouterError(
            "OPENROUTER_API_KEY is not configured. Add it to .env to run the equity agent."
        )
    model_id = model or settings.OPENROUTER_MODEL
    url = f"{settings.OPENROUTER_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/local/ai-cio",
        "X-Title": "AI-CIO Equity Decision Agent",
    }
    body = {
        "model": model_id,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(url, headers=headers, json=body)
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise OpenRouterError(f"OpenRouter HTTP {resp.status_code}: {resp.text[:500]}") from exc
        data = resp.json()

    try:
        message = data["choices"][0].get("message") or {}
    except (KeyError, IndexError, TypeError) as exc:
        raise OpenRouterError(f"Unexpected OpenRouter payload: {data!r}") from exc

    text = _message_text(message)
    if not text:
        raise OpenRouterError(
            f"OpenRouter returned empty content (finish_reason={data['choices'][0].get('finish_reason')!r})"
        )
    return text


def extract_json_object(text: str) -> dict[str, Any]:
    """Parse a JSON object from model output (allows fenced markdown)."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    candidates = [cleaned]
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        candidates.append(cleaned[start : end + 1])

    last_error: Exception | None = None
    for candidate in candidates:
        for payload in (candidate, "".join(ch if ord(ch) >= 32 or ch in "\n\r\t" else " " for ch in candidate)):
            try:
                data = json.loads(payload, strict=False)
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError as exc:
                last_error = exc
                continue
    raise OpenRouterError(
        f"Model response was not valid JSON object: {last_error}"
    )
