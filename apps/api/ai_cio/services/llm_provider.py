"""Facade for opportunity analysis via LLMProvider abstraction."""
from __future__ import annotations

import logging

from domain.market.contracts import MarketOpportunityAnalysis, OpportunityCandidate, TwinAnalysisContext

from ai_cio.llm.provider import DeterministicLLMProvider, get_llm_provider
from ai_cio.settings import LLM_ENABLED

logger = logging.getLogger(__name__)


def analyze_opportunity(
    *,
    candidate: OpportunityCandidate,
    twin_context: TwinAnalysisContext,
    sanitized_context: dict,
    market_facts: list[str],
    portfolio_facts: list[str],
    knowledge_refs: list[dict[str, str]],
) -> tuple[MarketOpportunityAnalysis, str]:
    """Returns (analysis, source) where source is 'litellm' or 'deterministic'."""
    provider = get_llm_provider()
    if isinstance(provider, DeterministicLLMProvider) or not LLM_ENABLED:
        return (
            provider.analyze_opportunity(
                candidate=candidate,
                context=sanitized_context,
                market_facts=market_facts,
                portfolio_facts=portfolio_facts,
                knowledge_refs=knowledge_refs,
            ),
            "deterministic",
        )
    try:
        analysis = provider.analyze_opportunity(
            candidate=candidate,
            context=sanitized_context,
            market_facts=market_facts,
            portfolio_facts=portfolio_facts,
            knowledge_refs=knowledge_refs,
        )
        return analysis, "litellm"
    except Exception as exc:
        logger.warning("llm_analysis_failed: %s", type(exc).__name__)
        fallback = DeterministicLLMProvider()
        return (
            fallback.analyze_opportunity(
                candidate=candidate,
                context=sanitized_context,
                market_facts=market_facts,
                portfolio_facts=portfolio_facts,
                knowledge_refs=knowledge_refs,
            ),
            "deterministic",
        )


def llm_health() -> dict:
    from ai_cio.llm.provider import DeterministicLLMProvider, LiteLLMProvider
    from ai_cio.settings import LLM_ENABLED

    if not LLM_ENABLED:
        return DeterministicLLMProvider().health()
    return LiteLLMProvider().health()
