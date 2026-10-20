"""Source grounding and missing-data boundaries; no database or provider calls."""
from datetime import date
from unittest.mock import patch

from ai_cio.services import finance_standards as standards
from ai_cio.services.agents.skills_loader import (
    DEFAULT_SKILL_NAMES, EQUITY_AGENT_SKILL_NAMES, load_domain_skills, skill_evidence_stubs,
)
from ai_cio.services.agents.equity_agent import EquityAgentAnalyzer
from ai_cio.services.knowledge_retriever import retrieve_knowledge
from domain.decision.contracts import DecisionObjective, InvestmentContext


def test_manifest_sources_have_scope_and_current_review_metadata():
    sources = standards.source_context_for_skills(DEFAULT_SKILL_NAMES, as_of=date(2026, 10, 20))
    assert {s["id"] for s in sources} >= {"cfa_suitability", "dicgc_guide", "tax_act_transition", "nism_retirement"}
    assert all(s["url"].startswith("https://") and s["scope"] and not s["review_due"] for s in sources)
    assert standards.source_context_for_skills(("not-a-finance-skill",)) == []


def test_sources_outside_review_window_are_not_silently_current():
    sources = standards.source_context_for_skills(("tax-source-discipline",), as_of=date(2026, 12, 1))
    assert len(sources) == 1 and sources[0]["review_due"] is True
    future = standards.source_context_for_skills(("tax-source-discipline",), as_of=date(2026, 10, 1))
    assert future[0]["review_due"] is True


def test_missing_manifest_fails_closed(tmp_path, monkeypatch):
    bad = tmp_path / "broken.json"
    bad.write_text("not JSON", encoding="utf-8")
    monkeypatch.setattr(standards, "SOURCE_MANIFEST", bad)
    assert standards.source_context_for_skills(DEFAULT_SKILL_NAMES) == []
    assert standards.load_source_manifest()["version"] == "unavailable"


def test_skill_pack_retains_frameworks_and_excludes_tooling_or_path_traversal():
    assert set(EQUITY_AGENT_SKILL_NAMES) == {"equity-analysis-first-principles", "portfolio-first-principles"}
    assert "tax-source-discipline" not in EQUITY_AGENT_SKILL_NAMES
    assert load_domain_skills(("pre-commit-verify", "../../README")) == ""
    text = load_domain_skills(("tax-source-discipline",))
    assert not text.startswith("---") and "name: tax-source" not in text
    evidence = skill_evidence_stubs(("tax-source-discipline",))
    assert evidence[0]["reference"].endswith("tax-source-discipline/SKILL.md")
    assert "tax_act_transition" in evidence[0]["content"]
    assert evidence[0]["relevance"] == "educational_framework_available"


def test_zero_is_known_but_nan_bool_and_missing_are_not_financial_facts():
    twin = {"financial_position": {"income": {"value": "0", "known": True}, "expenses": {"value": "NaN"}, "liquid": {"value": True}}}
    ctx = standards.build_finance_review_context(twin, EQUITY_AGENT_SKILL_NAMES)
    assert ctx["known_amount_fields"] == ["income"]
    missing = " ".join(ctx["required_missing_information"])
    assert "expenses amount" in missing and "liquid amount" in missing
    assert "income amount is missing" not in missing
    assert ctx["risk_capacity_status"] == "not_fully_assessed"


def test_occupation_and_willingness_do_not_invent_capacity():
    twin = {"user": {"name": "Tom", "occupation": "IAS"}, "behaviour": {"status": "known", "scores": {"risk_score": 90}}}
    ctx = standards.build_finance_review_context(twin, EQUITY_AGENT_SKILL_NAMES)
    assert ctx["declared_willingness_status"] == "recorded"
    assert ctx["risk_capacity_status"] == "not_fully_assessed"
    assert ctx["known_amount_fields"] == []
    assert any("cost basis" in s for s in ctx["required_missing_information"])


def test_model_sources_resolve_to_supplied_metadata_not_model_authored_claims():
    allowed = standards.source_context_for_skills(("tax-source-discipline",), as_of=date(2026, 10, 20))
    claims = [{"source_id": "invented-law", "content": "Guaranteed zero tax"}, {"source_id": "tax_act_transition", "url": "https://evil.invalid", "content": "A made-up tax exemption"}, {"source_id": "tax_act_transition"}]
    rows = standards.resolve_model_knowledge_claims(claims, allowed)
    assert len(rows) == 1
    assert rows[0]["reference"].startswith("https://www.incometax.gov.in/")
    assert "evil" not in str(rows) and "made-up" not in str(rows) and "Guaranteed" not in str(rows)
    assert standards.resolve_model_knowledge_claims([{"source_id": "tax_act_transition"}], []) == []


def test_retrieved_knowledge_carries_real_source_ids_and_versions():
    rows = retrieve_knowledge(topics=["tax", "liquidity", "retirement"], limit=3)
    assert len(rows) == 3
    assert rows[0]["source_ids"] == ["tax_act_transition"]
    assert "incometax.gov.in" in rows[0]["text"]
    assert all(row["version"] == "finance-standards-v1" for row in rows)
    assert retrieve_knowledge(topics=["tax"], limit=0) == []


def test_empty_holdings_never_calls_model_or_market_and_preserves_missing_inputs():
    context = InvestmentContext(user_id=1, decision_id="empty", objective=DecisionObjective.REVIEW_EQUITY_PORTFOLIO, twin={}, market_context={}, knowledge_evidence=[], decision_parameters={}, completeness={})
    with patch("ai_cio.services.agents.equity_agent.chat_completion") as chat, patch("ai_cio.services.agents.equity_agent.fetch_sector_day_changes") as feed, patch("ai_cio.services.agents.equity_agent.build_portfolio_dashboard", return_value={}):
        result = EquityAgentAnalyzer().analyze(context, capabilities=[])
    chat.assert_not_called()
    feed.assert_not_called()
    assert result.observations == []
    assert result.recommended_actions == []
    assert any("No holdings" in text for text in result.missing_information)
    assert result.candidate_strategies[0].expected_characteristics["confidence"] == "low"
    assert all(e.reference != "model_cited" for e in result.evidence)


def test_model_claimed_authority_and_high_confidence_cannot_fill_missing_capacity():
    twin = {"portfolio": {"holdings": [{"scheme_name": "Synthetic holding", "asset_class": "equity", "valuation": "10"}]}}
    context = InvestmentContext(user_id=1, decision_id="partial", objective=DecisionObjective.REVIEW_EQUITY_PORTFOLIO, twin=twin, market_context={}, knowledge_evidence=[], decision_parameters={}, completeness={})
    raw = '{"observations": [], "recommended_actions": [], "confidence": "high", "knowledge_used": [{"source_id": "invented_source", "content": "Guaranteed outperformance"}]}'
    with patch("ai_cio.services.agents.equity_agent.chat_completion", return_value=raw), patch("ai_cio.services.agents.equity_agent.fetch_sector_day_changes", return_value={"available": False}), patch("ai_cio.services.agents.equity_agent.build_portfolio_dashboard", return_value={}):
        result = EquityAgentAnalyzer().analyze(context, capabilities=[])
    assert result.candidate_strategies[0].expected_characteristics["confidence"] == "low"
    assert any("income amount" in text for text in result.missing_information)
    assert not any("Guaranteed outperformance" in e.content for e in result.evidence)


def test_real_empty_dashboard_does_not_turn_missing_holdings_into_concentration_risk():
    context = InvestmentContext(user_id=1, decision_id="empty-real", objective=DecisionObjective.REVIEW_EQUITY_PORTFOLIO, twin={}, market_context={}, knowledge_evidence=[], decision_parameters={}, completeness={})
    with patch("ai_cio.services.agents.equity_agent.chat_completion") as chat:
        result = EquityAgentAnalyzer().analyze(context, capabilities=[])
    chat.assert_not_called()
    assert "concentration" not in result.decision_summary.lower()
    assert "records" in result.decision_summary.lower()
    assert any("No holdings" in text for text in result.missing_information)
