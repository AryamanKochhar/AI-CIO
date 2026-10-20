"""Independent deterministic bond specialist for the central parallel join."""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from ai_cio import settings
from ai_cio.services.bonds.analysis import analyse_bonds


def run_bond_agent(twin: dict, *, provider=None, as_of: date | None = None) -> dict:
    today = as_of or datetime.now(ZoneInfo("Asia/Kolkata")).date()
    if not getattr(settings, "BOND_AGENT_ENABLED", True):
        return {"version": "bond-intelligence-v1", "agent": "bond_agent", "available": False,
                "status": "disabled", "as_of": today.isoformat(), "summary": "Bond Agent is disabled.",
                "holdings": [], "catalogue_products": [], "eligible_products": [], "excluded_products": [],
                "findings": [], "sources": [], "data_quality": {"next_action": "Enable the Bond Agent to review verified issue terms."},
                "methods": {}, "constraint_policy": {}}
    return analyse_bonds(twin, provider=provider, as_of=today)
