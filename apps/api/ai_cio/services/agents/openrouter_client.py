"""Chat completions client for decision agents (OpenAI or OpenRouter)."""
from __future__ import annotations

import json
import logging
from time import perf_counter
from typing import Any

import httpx

from ai_cio import settings
from ai_cio.services.orchestration.runtime import active_run, note_json_validation, sanitize_llm_messages

logger = logging.getLogger(__name__)


class OpenRouterError(RuntimeError):
    """Raised when the configured LLM provider fails (name kept for callers)."""

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
    timeout: float = 45.0,
) -> str:
    provider = settings.equity_llm_provider()
    api_key = settings.equity_llm_api_key()
    if not api_key:
        raise OpenRouterError(
            f"No API key for provider={provider!r}. "
            "Set OPENAI_API_KEY (or OPEN_API_KEY) / OPENROUTER_API_KEY in .env."
        )
    model_id = model or settings.equity_llm_model()
    base_url = settings.equity_llm_base_url()
    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if provider == "openrouter":
        headers["HTTP-Referer"] = "https://github.com/local/ai-cio"
        headers["X-Title"] = "AI-CIO Equity Decision Agent"
    body = {
        "model": model_id,
        "messages": sanitize_llm_messages(messages),
        "temperature": temperature,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }
    logger.info("equity_llm_chat provider=%s model=%s", provider, model_id)
    active = active_run()
    call_id = active[0].begin_llm(active[1], body, provider) if active else None
    began = perf_counter()
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, headers=headers, json=body)
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise OpenRouterError(f"{provider} HTTP {resp.status_code}; provider response body withheld") from exc
            data = resp.json()
        if not isinstance(data, dict) or data.get("error"):
            raise OpenRouterError(f"Unexpected {provider} response schema")
        try:
            message = data["choices"][0].get("message") or {}
        except (KeyError, IndexError, TypeError) as exc:
            raise OpenRouterError(f"Unexpected {provider} response schema") from exc
        text = _message_text(message)
        if not text:
            raise OpenRouterError(f"{provider} returned empty content")
        if active and call_id:
            active[0].finish_llm(call_id, started=began, text=text)
        return text
    except Exception as exc:
        if active and call_id:
            active[0].finish_llm(call_id, started=began, error=type(exc).__name__)
        if isinstance(exc, OpenRouterError):
            raise
        raise OpenRouterError(f"{provider} transport unavailable ({type(exc).__name__})") from exc


def extract_json_object(text: str) -> dict[str, Any]:
    """Parse a JSON object from model output (allows fenced markdown + light repair)."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    # Prefer the outermost object span when present
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        cleaned = cleaned[start : end + 1]

    candidates = [cleaned, _repair_jsonish(cleaned)]
    last_error: Exception | None = None
    for candidate in candidates:
        for payload in (
            candidate,
            "".join(ch if ord(ch) >= 32 or ch in "\n\r\t" else " " for ch in candidate),
        ):
            try:
                data = json.loads(payload, strict=False)
                if isinstance(data, dict):
                    note_json_validation(True)
                    return data
            except json.JSONDecodeError as exc:
                last_error = exc
                continue

    # Last resort: truncated object — close open braces/brackets and retry
    closed = _close_truncated_json(_repair_jsonish(cleaned))
    if closed:
        try:
            data = json.loads(closed, strict=False)
            if isinstance(data, dict):
                note_json_validation(True)
                return data
        except json.JSONDecodeError as exc:
            last_error = exc

    note_json_validation(False)
    raise OpenRouterError(f"Model response was not valid JSON object: {last_error}")


def _repair_jsonish(text: str) -> str:
    """Best-effort fixes for common LLM JSON mistakes."""
    import re

    fixed = text.replace("\u201c", '"').replace("\u201d", '"').replace("\u2019", "'")
    # Trailing commas before } or ]
    fixed = re.sub(r",\s*([}\]])", r"\1", fixed)
    return fixed


def _close_truncated_json(text: str) -> str | None:
    """If the model truncated mid-object, close open quotes/brackets conservatively."""
    if not text or "{" not in text:
        return None
    in_string = False
    escape = False
    stack: list[str] = []
    out: list[str] = []
    for ch in text:
        out.append(ch)
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch in "{[":
            stack.append("}" if ch == "{" else "]")
        elif ch in "}]":
            if stack and stack[-1] == ch:
                stack.pop()
    if in_string:
        out.append('"')
    while stack:
        out.append(stack.pop())
    candidate = "".join(out)
    # Drop a trailing dangling comma before the closers we added
    import re

    candidate = re.sub(r",(\s*[}\]])+$", lambda m: m.group(0).lstrip(","), candidate)
    candidate = re.sub(r",\s*([}\]])", r"\1", candidate)
    return candidate
