"""Mutual Fund specialist: deterministic first principles, no database session.

The central coordinator supplies one immutable Twin snapshot alongside the
other parallel specialists, then reconciles and validates their findings.
"""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from ai_cio import settings

from ai_cio.services.mutual_funds.analysis import analyse_mutual_funds


def run_mutual_fund_agent(twin: dict, *, provider=None, as_of: date | None = None) -> dict:
    if not settings.MUTUAL_FUND_AGENT_ENABLED:
        today = as_of or datetime.now(ZoneInfo("Asia/Kolkata")).date()
        return {"result_version": "mf-intelligence-v1", "available": False, "agent": "mutual_fund_agent",
                "status": "disabled", "as_of": today.isoformat(), "summary": "Mutual Fund Agent is disabled in application configuration.",
                "funds": [], "overlaps": [], "correlations": [], "findings": [], "sources": [],
                "combined_exposure": {"status": "unavailable", "known_coverage_pct": None, "unmapped_value": None,
                                      "securities": [], "note": "MF analysis is disabled; no portfolio-health conclusion is inferred."},
                "data_quality": {"warnings": ["MUTUAL_FUND_AGENT_ENABLED is false"], "missing": ["Mutual fund analysis is disabled"],
                                 "budget": {}, "psychometrics": {}, "coverage": {"funds": 0}},
                "methods": {}}
    return analyse_mutual_funds(twin, provider=provider, as_of=as_of)
