"""LLMProvider → LiteLLMProvider. Model gateway only — no financial calculations."""
from __future__ import annotations

import json
import logging
import re
import time
from abc import ABC, abstractmethod
from typing import Any

from domain.market.contracts import MarketOpportunityAnalysis, OpportunityCandidate

from ai_cio.settings import (
    LITELLM_API_KEY,
    LITELLM_BASE_URL,
    LLM_ENABLED,
    LLM_MODEL,
    OPPORTUNITY_ANALYSIS_PROMPT_VERSION,
)

logger = logging.getLogger(__name__)

FORBIDDEN_OUTPUT_PHRASES = (
    "buy now",
    "sell now",
    "guaranteed",
    "risk-free",
    "certain return",
    "definitely buy",
    "definitely sell",
)


class LLMProvider(ABC):
    @abstractmethod
    def analyze_opportunity(
        self,
        *,
        candidate: OpportunityCandidate,
        context: dict[str, Any],
        market_facts: list[str],
        portfolio_facts: list[str],
        knowledge_refs: list[dict[str, str]],
    ) -> MarketOpportunityAnalysis:
        ...

    @abstractmethod
    def health(self) -> dict[str, Any]:
        ...


def _extract_json(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def _validate_analysis(data: dict[str, Any], candidate: OpportunityCandidate) -> list[str]:
    issues: list[str] = []
    required = ("summary", "why_relevant", "confidence", "recommended_next_step")
    for field in required:
        if not data.get(field):
            issues.append(f"missing:{field}")
    blob = json.dumps(data).lower()
    for phrase in FORBIDDEN_OUTPUT_PHRASES:
        if phrase in blob:
            issues.append(f"forbidden:{phrase}")
    if data.get("opportunity_type") and data["opportunity_type"] != candidate.type:
        issues.append("type_mismatch")
    return issues


class LiteLLMProvider(LLMProvider):
    def __init__(self) -> None:
        self._base = (LITELLM_BASE_URL or "").rstrip("/")
        self._api_key = LITELLM_API_KEY
        self._model = LLM_MODEL

    def health(self) -> dict[str, Any]:
        enabled = LLM_ENABLED
        configured = bool(self._base and self._api_key and self._model)
        status = {
            "enabled": enabled,
            "configured": configured,
            "model_configured": bool(self._model),
            "reachable": False,
            "test_successful": False,
        }
        if not enabled:
            status["status"] = "disabled"
            return status
        if not configured:
            status["status"] = "misconfigured"
            return status
        try:
            import httpx

            r = httpx.get(
                f"{self._base}/v1/models",
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=10.0,
            )
            status["reachable"] = r.status_code < 500
            if r.status_code == 200:
                status["test_successful"] = True
                status["status"] = "ok"
            elif r.status_code in (401, 403):
                status["status"] = "auth_failed"
            else:
                status["status"] = "unavailable"
        except Exception:
            status["status"] = "unavailable"
        return status

    def analyze_opportunity(
        self,
        *,
        candidate: OpportunityCandidate,
        context: dict[str, Any],
        market_facts: list[str],
        portfolio_facts: list[str],
        knowledge_refs: list[dict[str, str]],
    ) -> MarketOpportunityAnalysis:
        import litellm  # type: ignore

        payload = {
            "candidate": {
                "type": candidate.type,
                "sector": candidate.sector_name,
                "sector_index_code": candidate.sector_index_code,
                "market_move_percent": str(candidate.market_move_percent),
                "benchmark_move_percent": str(candidate.benchmark_move_percent),
                "relative_move_percent": str(candidate.relative_move_percent),
                "user_exposure_percent": str(candidate.user_exposure_percent),
                "user_exposure_value": str(candidate.user_exposure_value),
            },
            "sanitized_context": context,
            "market_facts": market_facts,
            "portfolio_facts": portfolio_facts,
            "knowledge": [
                {k: v for k, v in ref.items() if k in ("source", "title", "section", "reference", "text")}
                for ref in knowledge_refs
            ],
            "prompt_version": OPPORTUNITY_ANALYSIS_PROMPT_VERSION,
        }
        system = (
            "You are AI-CIO market intelligence analyst. Respond with JSON only. "
            "Use ONLY facts in the user payload. Do NOT calculate numbers. "
            "Do NOT recommend buy or sell. "
            "JSON fields: opportunity_type, summary, why_relevant[], market_facts[], "
            "portfolio_facts[], considerations[], risks[], missing_information[], "
            "knowledge_references[], confidence, recommended_next_step."
        )
        started = time.perf_counter()
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(payload)},
            ],
            "api_key": self._api_key,
            "api_base": self._base,
            "timeout": 60,
        }
        response = litellm.completion(**kwargs)
        latency_ms = int((time.perf_counter() - started) * 1000)
        logger.info("llm_call model=%s latency_ms=%s", self._model, latency_ms)
        content = response.choices[0].message.content or ""
        data = _extract_json(content)
        issues = _validate_analysis(data, candidate)
        if issues:
            raise ValueError(f"invalid_llm_output:{','.join(issues)}")
        return MarketOpportunityAnalysis(
            opportunity_type=data.get("opportunity_type", candidate.type),
            summary=str(data.get("summary", "")),
            why_relevant=list(data.get("why_relevant") or []),
            market_facts=list(data.get("market_facts") or market_facts),
            portfolio_facts=list(data.get("portfolio_facts") or portfolio_facts),
            risks=list(data.get("risks") or []),
            missing_information=list(data.get("missing_information") or []),
            knowledge_references=list(data.get("knowledge_references") or knowledge_refs),
            confidence=str(data.get("confidence") or "medium"),
            recommended_next_step=str(data.get("recommended_next_step") or ""),
        )


class DeterministicLLMProvider(LLMProvider):
    """Fallback when LLM disabled or unavailable."""

    def health(self) -> dict[str, Any]:
        return {
            "enabled": False,
            "configured": False,
            "reachable": False,
            "model_configured": bool(LLM_MODEL),
            "test_successful": False,
            "status": "disabled",
        }

    def analyze_opportunity(
        self,
        *,
        candidate: OpportunityCandidate,
        context: dict[str, Any],
        market_facts: list[str],
        portfolio_facts: list[str],
        knowledge_refs: list[dict[str, str]],
    ) -> MarketOpportunityAnalysis:
        sector = candidate.sector_name or "the market"
        summary = f"{sector} moved {candidate.market_move_percent}% today"
        if candidate.relative_move_percent is not None:
            summary += f" (relative to benchmark: {candidate.relative_move_percent} percentage points)."
        return MarketOpportunityAnalysis(
            opportunity_type=candidate.type,
            summary=summary,
            why_relevant=[
                "The sector moved materially relative to the broader market.",
                "You have identified exposure in this area of your portfolio.",
            ],
            market_facts=market_facts,
            portfolio_facts=portfolio_facts,
            risks=["Past performance does not guarantee future results."],
            missing_information=list(context.get("missing_information") or []),
            knowledge_references=knowledge_refs,
            confidence="medium",
            recommended_next_step="Review your objectives, time horizon, and concentration before taking action.",
        )


def get_llm_provider() -> LLMProvider:
    if LLM_ENABLED and LITELLM_BASE_URL and LITELLM_API_KEY and LLM_MODEL:
        return LiteLLMProvider()
    return DeterministicLLMProvider()
