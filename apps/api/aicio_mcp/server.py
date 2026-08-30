"""CAS Financial Intelligence MCP server (stdio). Reads canonical Postgres."""
from __future__ import annotations

from decimal import Decimal

from mcp.server.fastmcp import FastMCP

from domain.analysis import allocation, concentration_metrics, sip_summary, top_holdings, total_value
from ai_cio.db.session import get_session
from ai_cio.services.assessments import SCORE_FIELDS, latest_profile
from ai_cio.services.identity import resolve_user_id
from ai_cio.services.instruments import DomainError
from ai_cio.services.portfolio import holdings_on_page, list_holdings, list_transactions
from ai_cio.settings import KNOWLEDGE_DIR

mcp = FastMCP("CAS Financial Intelligence")


def serialise(value):
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    if isinstance(value, list):
        return [serialise(x) for x in value]
    if isinstance(value, dict):
        return {k: serialise(v) for k, v in value.items()}
    return value


def _db():
    return get_session()


@mcp.tool()
def get_holdings(user_id: int | None = None, document_id: int | None = None) -> list[dict]:
    """Return parsed current holdings for a user. Defaults to the latest CAS document. Raw page text is not returned."""
    db = _db()
    try:
        uid = resolve_user_id(db, user_id)
        return serialise(list_holdings(db, uid, document_id))
    except DomainError as exc:
        raise RuntimeError(str(exc)) from exc
    finally:
        db.close()


@mcp.tool()
def get_portfolio_summary(user_id: int | None = None, document_id: int | None = None) -> dict:
    """Return deterministic valuation, allocations, rankings, and concentration measurements."""
    db = _db()
    try:
        uid = resolve_user_id(db, user_id)
        hs = list_holdings(db, uid, document_id)
        amcs = allocation(hs, "amc")
        ranked = top_holdings(hs, 5)
        return serialise(
            {
                "user_id": uid,
                "total_portfolio_value": total_value(hs),
                "number_of_funds": len(hs),
                "amc_allocation": amcs,
                "fund_allocation": top_holdings(hs, len(hs)),
                "largest_holding": ranked[:1],
                "largest_amc_exposure": amcs[:1],
                "top_3_holdings": ranked[:3],
                "top_5_holdings": ranked,
                "concentration_metrics": concentration_metrics(hs),
            }
        )
    except DomainError as exc:
        raise RuntimeError(str(exc)) from exc
    finally:
        db.close()


@mcp.tool()
def get_transactions(
    user_id: int | None = None,
    document_id: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    fund: str | None = None,
    amc: str | None = None,
    transaction_type: str | None = None,
) -> list[dict]:
    """Filter transactions; dates use the CAS date format stored by the parser."""
    db = _db()
    try:
        uid = resolve_user_id(db, user_id)
        return serialise(
            list_transactions(db, uid, document_id, start_date, end_date, fund, amc, transaction_type)
        )
    except DomainError as exc:
        raise RuntimeError(str(exc)) from exc
    finally:
        db.close()


@mcp.tool()
def get_sips(user_id: int | None = None, document_id: int | None = None) -> dict:
    """Return SIP activity; failed payments are separated and never included in purchases."""
    db = _db()
    try:
        uid = resolve_user_id(db, user_id)
        rows = list_transactions(db, uid, document_id)
        relevant = [
            x
            for x in rows
            if x["transaction_type"] in {"SIP_PURCHASE", "FAILED_PAYMENT", "SIP_CANCELLED", "SIP_REGISTERED"}
        ]
        return serialise({"activity": relevant, "summary": sip_summary(rows)})
    except DomainError as exc:
        raise RuntimeError(str(exc)) from exc
    finally:
        db.close()


@mcp.tool()
def search_knowledge(query: str) -> list[dict]:
    """Keyword search of local educational Markdown. Not personalised financial advice."""
    terms = {x.lower() for x in query.split() if len(x) > 2}
    results = []
    for path in KNOWLEDGE_DIR.glob("*.md"):
        text = path.read_text()
        lines = [line for line in text.splitlines() if terms & set(line.lower().split())]
        if lines:
            results.append({"document": path.name, "matches": lines[:8]})
    return results


@mcp.tool()
def get_source(page: int, user_id: int | None = None, document_id: int | None = None) -> dict:
    """Return holdings linked to a CAS page. Raw source text is not exposed."""
    db = _db()
    try:
        uid = resolve_user_id(db, user_id)
        return serialise(holdings_on_page(db, uid, page, document_id))
    except DomainError as exc:
        raise RuntimeError(str(exc)) from exc
    finally:
        db.close()


@mcp.tool()
def get_behavioral_profile(user_id: int | None = None, session_id: int | None = None) -> dict:
    """Return the stored behavioural profile for a user. Does not re-score and does not include raw answers."""
    db = _db()
    try:
        uid = resolve_user_id(db, user_id)
        if session_id is not None:
            from ai_cio.services.assessments import get_profile

            profile = get_profile(db, session_id)
            if profile.user_id != uid:
                raise RuntimeError("Profile does not belong to this user")
        else:
            profile = latest_profile(db, uid)
        payload = {
            "id": profile.id,
            "user_id": profile.user_id,
            "session_id": profile.session_id,
            "instrument_id": profile.instrument_id,
            "polarity": profile.polarity,
        }
        for field in SCORE_FIELDS:
            payload[field] = getattr(profile, field)
        payload["average_confidence"] = profile.average_confidence
        payload["average_response_time_ms"] = profile.average_response_time_ms
        payload["profile_confidence"] = profile.profile_confidence
        return serialise(payload)
    except DomainError as exc:
        raise RuntimeError(str(exc)) from exc
    finally:
        db.close()


if __name__ == "__main__":
    mcp.run()
