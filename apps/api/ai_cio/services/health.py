"""Application health checks."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from ai_cio.services.llm_provider import llm_health


def build_health_payload(db: Session) -> dict:
    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    llm = llm_health()
    llm_public = {
        "enabled": llm.get("enabled"),
        "configured": llm.get("configured"),
        "reachable": llm.get("reachable"),
        "model_configured": llm.get("model_configured"),
        "status": llm.get("status", "disabled"),
    }

    status = "ok" if db_ok else "degraded"
    return {
        "status": status,
        "database": "ok" if db_ok else "unavailable",
        "market_intelligence": "available",
        "llm": llm_public["status"] if llm_public["enabled"] else "disabled",
        "llm_details": llm_public,
    }
