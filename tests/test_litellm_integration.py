"""LiteLLM integration tests — configuration, security, and failure paths."""
from __future__ import annotations

import json
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from ai_cio.llm.provider import (
    DeterministicLLMProvider,
    LiteLLMProvider,
    _validate_analysis,
    get_llm_provider,
)
from ai_cio.services.llm_provider import analyze_opportunity, llm_health
from ai_cio.services.notifications import build_market_observation_email, validate_email_content
from ai_cio.services.twin_context_builder import build_sanitized_analysis_context
from domain.market.contracts import OpportunityCandidate, TwinAnalysisContext

pytestmark = pytest.mark.integration


def _candidate() -> OpportunityCandidate:
    return OpportunityCandidate(
        type="sector_move",
        sector_index_code="NIFTY IT",
        sector_name="Information Technology",
        market_move_percent=Decimal("-3.2"),
        benchmark_move_percent=Decimal("-0.8"),
        relative_move_percent=Decimal("-2.4"),
        user_exposure_percent=Decimal("18.4"),
        user_exposure_value=Decimal("240000"),
        reason_codes=["sector_change", "relative_move", "exposure"],
        severity="information",
    )


def test_llm_disabled_uses_deterministic_provider():
    with patch("ai_cio.llm.provider.LLM_ENABLED", False):
        provider = get_llm_provider()
        assert isinstance(provider, DeterministicLLMProvider)


def test_llm_misconfigured_when_model_missing():
    with patch("ai_cio.llm.provider.LLM_ENABLED", True), patch(
        "ai_cio.llm.provider.LITELLM_BASE_URL", "https://example.com"
    ), patch("ai_cio.llm.provider.LITELLM_API_KEY", "secret-key"), patch("ai_cio.llm.provider.LLM_MODEL", ""):
        provider = get_llm_provider()
        assert isinstance(provider, DeterministicLLMProvider)
        health = LiteLLMProvider().health()
        assert health["enabled"] is True
        assert health["configured"] is False
        assert health["status"] == "misconfigured"


def test_health_never_exposes_api_key():
    with patch("ai_cio.llm.provider.LLM_ENABLED", True), patch(
        "ai_cio.llm.provider.LITELLM_BASE_URL", "https://example.com"
    ), patch("ai_cio.llm.provider.LITELLM_API_KEY", "super-secret-key"), patch(
        "ai_cio.llm.provider.LLM_MODEL", "kimi"
    ), patch("httpx.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=200)
        payload = llm_health()
    blob = json.dumps(payload).lower()
    assert "super-secret-key" not in blob
    assert "api_key" not in blob
    assert "authorization" not in blob


def test_validate_analysis_rejects_forbidden_phrases():
    issues = _validate_analysis(
        {
            "summary": "Buy now before it is too late",
            "why_relevant": ["x"],
            "confidence": "high",
            "recommended_next_step": "review",
        },
        _candidate(),
    )
    assert any("forbidden" in i for i in issues)


def test_analyze_opportunity_falls_back_on_llm_failure():
    candidate = _candidate()
    twin_ctx = TwinAnalysisContext(portfolio={}, goals=[], behavioural={}, completeness={})
    sanitized = {"missing_information": []}
    with patch("ai_cio.services.llm_provider.LLM_ENABLED", True), patch(
        "ai_cio.services.llm_provider.get_llm_provider"
    ) as mock_provider:
        failing = MagicMock()
        failing.analyze_opportunity.side_effect = ValueError("invalid_llm_output")
        mock_provider.return_value = failing
        analysis, source = analyze_opportunity(
            candidate=candidate,
            twin_context=twin_ctx,
            sanitized_context=sanitized,
            market_facts=["IT: -3.2%"],
            portfolio_facts=["Exposure: 18.4%"],
            knowledge_refs=[],
        )
    assert source == "deterministic"
    assert "Information Technology" in analysis.summary


def test_analyze_opportunity_litellm_success():
    candidate = _candidate()
    twin_ctx = TwinAnalysisContext(portfolio={}, goals=[], behavioural={}, completeness={})
    sanitized = {"missing_information": []}
    mock_analysis = MagicMock()
    mock_analysis.summary = "Sector moved materially."
    with patch("ai_cio.services.llm_provider.LLM_ENABLED", True), patch(
        "ai_cio.services.llm_provider.get_llm_provider"
    ) as mock_provider:
        provider = MagicMock()
        provider.analyze_opportunity.return_value = mock_analysis
        mock_provider.return_value = provider
        analysis, source = analyze_opportunity(
            candidate=candidate,
            twin_context=twin_ctx,
            sanitized_context=sanitized,
            market_facts=["IT: -3.2%"],
            portfolio_facts=["Exposure: 18.4%"],
            knowledge_refs=[],
        )
    assert source == "litellm"
    assert analysis.summary == "Sector moved materially."


def test_sanitized_context_excludes_sensitive_fields():
    twin = {
        "portfolio": {"total_value": {"value": "1000000", "source": "cdsl"}},
        "goals": {"items": [{"name": "Retirement", "target_amount": "5000000"}]},
        "behaviour": {"status": "complete", "observations": []},
        "financial_position": {"liquid": {"known": True, "value": "200000"}},
        "completeness": {"portfolio": True, "goals": True},
        "pan": "ABCDE1234F",
        "aadhaar": "1234-5678-9012",
        "raw_cas": "CONFIDENTIAL CAS TEXT",
    }
    ctx = build_sanitized_analysis_context(
        twin=twin,
        sector_name="Information Technology",
        sector_exposure={"sectors": []},
        market_facts=["Source: NSE"],
    )
    blob = json.dumps(ctx)
    assert "ABCDE1234F" not in blob
    assert "1234-5678-9012" not in blob
    assert "CONFIDENTIAL CAS TEXT" not in blob
    assert "pan" not in blob.lower()


def test_email_rejects_forbidden_language():
    subject, body = build_market_observation_email(
        user_name="Test",
        sector_name="IT",
        sector_change="-3.2",
        benchmark_change="-0.8",
        relative_change="-2.4",
        exposure_value="100000",
        exposure_pct="10",
        why_surface=["Material move"],
        missing=[],
    )
    assert validate_email_content(subject, body) == []
    bad_subject, bad_body = build_market_observation_email(
        user_name="Test",
        sector_name="IT",
        sector_change="-3.2",
        benchmark_change="-0.8",
        relative_change="-2.4",
        exposure_value="100000",
        exposure_pct="10",
        why_surface=["Guaranteed return if you buy now"],
        missing=[],
    )
    assert validate_email_content(bad_subject, bad_body)


def test_health_endpoint_shape(client):
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert "status" in payload
    assert "database" in payload
    assert "llm" in payload
    assert "api_key" not in json.dumps(payload).lower()


def test_llm_health_endpoint(client):
    response = client.get("/health/llm")
    assert response.status_code == 200
    payload = response.json()
    assert "enabled" in payload
    assert "configured" in payload
    assert "api_key" not in json.dumps(payload).lower()
