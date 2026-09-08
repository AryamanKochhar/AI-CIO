"""Digital Financial Twin assembly.

The Twin is NOT a second database. It is an assembled, read-only representation
of a user's current financial state built from authoritative records in
PostgreSQL. Every important fact carries provenance and a known/unknown status.
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from domain.analysis import total_value
from ai_cio.psychometrics.polarity import DIMENSION_POLARITY
from ai_cio.services.assessments import SCORE_FIELDS, get_observations, latest_profile
from ai_cio.services.finances import serialize_finances
from ai_cio.services.goals import list_goals, serialize_goal
from ai_cio.services.identity import get_user
from ai_cio.services.instruments import DomainError
from ai_cio.services.journey import get_or_create_journey
from ai_cio.services.financial_map import build_financial_map
from ai_cio.services.portfolio import document_count, list_holdings, list_portfolio_snapshots
from ai_cio.db.models import Document


ZERO = Decimal("0")


def _money(value) -> Decimal | None:
    if value is None or value == "":
        return None
    return Decimal(str(value))


def _known(value) -> bool:
    return value not in (None, "", [], {})


def assemble_twin(db: Session, user_id: int) -> dict:
    """Build the canonical Digital Financial Twin for a user."""
    user = get_user(db, user_id)
    journey = get_or_create_journey(db, user_id)
    finances = serialize_finances(db, user_id)
    goals = [serialize_goal(row) for row in list_goals(db, user_id)]
    holdings = list_holdings(db, user_id)
    docs = document_count(db, user_id)
    snapshots = list_portfolio_snapshots(db, user_id)

    source_doc = None
    if holdings:
        doc_id = holdings[0].get("document_id")
        if doc_id:
            source_doc = db.query(Document).filter(Document.id == doc_id, Document.user_id == user_id).first()

    provenance = None
    if source_doc:
        meta = source_doc.metadata_json or {}
        kind_label = {
            "cas_pdf": "Mutual Fund CAS",
            "cdsl_statement": "CDSL CAS",
            "nsdl_statement": "NSDL statement",
        }.get(source_doc.kind, source_doc.kind)
        provenance = {
            "source": kind_label,
            "document_id": source_doc.id,
            "filename": source_doc.filename,
            "period_start": meta.get("statement_start"),
            "period_end": meta.get("statement_end"),
            "last_processed": source_doc.ingested_at.isoformat() if source_doc.ingested_at else None,
            "cas_id": meta.get("cas_id"),
        }

    # Behaviour
    behaviour = {"status": "unknown", "source": None, "scores": None, "observations": []}
    try:
        profile = latest_profile(db, user_id)
        scores = {field: getattr(profile, field) for field in SCORE_FIELDS}
        behaviour = {
            "status": "known",
            "source": "psychometric_assessment",
            "provenance": {
                "session_id": profile.session_id,
                "instrument_id": profile.instrument_id,
                "instrument_version": profile.instrument.payload.get("version") if profile.instrument else None,
            },
            "scores": scores,
            "polarity": profile.polarity,
            "profile_confidence": profile.profile_confidence,
            "observations": get_observations(db, profile.session_id),
        }
    except DomainError:
        pass

    # Financial position
    income = _money(finances.get("income"))
    expenses = _money(finances.get("expenses"))
    liquid = _money(finances.get("liquid"))
    liabilities = finances.get("liabilities") or []
    liability_total = sum((_money(item["balance"]) or ZERO for item in liabilities), ZERO)
    monthly_payments = sum((_money(item.get("monthly_payment")) or ZERO for item in liabilities), ZERO)
    net_worth = (liquid or ZERO) - liability_total

    portfolio_value = total_value(holdings) if holdings else None
    if portfolio_value is not None:
        net_worth += portfolio_value

    goal_items = [
        {
            **goal,
            "target_amount": _money(goal.get("target_amount")),
            "current_funding": _money(goal.get("current_funding")),
        }
        for goal in goals
    ]

    # Explicit completeness map
    completeness = {
        "psychometric": behaviour["status"] == "known",
        "income": _known(finances.get("income")),
        "expenses": _known(finances.get("expenses")),
        "liquid": _known(finances.get("liquid")),
        "liabilities": bool(liabilities) or journey.finances_status == "provided",
        "goals": bool(goal_items),
        "portfolio": bool(holdings),
        "horizon": any(goal.get("target_date") or goal.get("horizon_years") for goal in goal_items),
    }

    equity_holdings = [row for row in holdings if row.get("asset_class") == "equity" or row.get("amc") == "EQUITY"]
    mf_holdings = [row for row in holdings if row not in equity_holdings]
    source_label = provenance["source"] if provenance else ("document-derived" if holdings else None)

    financial_map = build_financial_map(
        user_name=user.name,
        income=income,
        expenses=expenses,
        liquid=liquid,
        liabilities=liabilities,
        liability_total=liability_total,
        holdings=holdings,
        goals=goal_items,
        behaviour=behaviour,
        completeness=completeness,
        provenance=provenance,
        portfolio_value=portfolio_value,
    )

    payload = {
        "user": {
            "id": user.id,
            "name": user.name,
            "source": "user-provided",
        },
        "behaviour": behaviour,
        "financial_position": {
            "income": {"value": f"{income:.2f}" if income is not None else None, "source": "user-provided", "known": income is not None},
            "expenses": {"value": f"{expenses:.2f}" if expenses is not None else None, "source": "user-provided", "known": expenses is not None},
            "liquid": {"value": f"{liquid:.2f}" if liquid is not None else None, "source": "user-provided", "known": liquid is not None},
            "liabilities": {
                "items": finances.get("liabilities", []),
                "total_balance": f"{liability_total:.2f}",
                "monthly_payments": f"{monthly_payments:.2f}",
                "source": "user-provided",
                "known": bool(liabilities) or journey.finances_status == "provided",
            },
            "net_worth": {"value": f"{net_worth:.2f}", "source": "system-calculated", "known": income is not None or liquid is not None or bool(holdings)},
        },
        "portfolio": {
            "document_count": docs,
            "holdings_count": len(holdings),
            "equity_count": len(equity_holdings),
            "mutual_fund_count": len(mf_holdings),
            "total_value": {
                "value": f"{portfolio_value:.2f}" if portfolio_value is not None else None,
                "source": source_label,
                "known": bool(holdings),
            },
            "provenance": provenance,
            "snapshots": [
                {
                    "month_year": s["month_year"],
                    "valuation": f"{s['valuation']:.2f}",
                    "change_amount": f"{s['change_amount']:.2f}" if s.get("change_amount") is not None else None,
                    "change_pct": f"{s['change_pct']:.2f}" if s.get("change_pct") is not None else None,
                }
                for s in snapshots
            ],
            "holdings": [
                {
                    "amc": row["amc"],
                    "scheme_name": row["scheme_name"],
                    "isin": row.get("isin"),
                    "folio": row.get("folio"),
                    "closing_units": f"{row['closing_units']:.4f}",
                    "nav": f"{row['nav']:.2f}",
                    "valuation": f"{row['valuation']:.2f}",
                    "valuation_date": row.get("valuation_date"),
                    "asset_class": row.get("asset_class"),
                    "invested_amount": f"{row['invested_amount']:.2f}" if row.get("invested_amount") is not None else None,
                    "unrealised_pl": f"{row['unrealised_pl']:.2f}" if row.get("unrealised_pl") is not None else None,
                    "unrealised_pl_pct": f"{row['unrealised_pl_pct']:.2f}" if row.get("unrealised_pl_pct") is not None else None,
                    "source_page": row["source_page"],
                    "source": source_label,
                    "document_id": row["document_id"],
                }
                for row in holdings
            ],
        },
        "goals": {
            "items": goal_items,
            "source": "user-provided",
            "known": bool(goal_items),
        },
        "completeness": completeness,
        "financial_map": financial_map,
        "dimension_labels": {
            name: spec["higher_means"] for name, spec in DIMENSION_POLARITY.items()
        },
        "ready_for_analysis": all(
            completeness[key] for key in ("psychometric", "income", "expenses", "liquid", "goals", "portfolio")
        ),
    }
    try:
        from ai_cio.services.market_context import build_market_context

        payload["market_context"] = build_market_context(db, user_id)
    except Exception:
        payload["market_context"] = {
            "available": False,
            "note": "Market context is temporarily unavailable.",
            "freshness": "unavailable",
            "source": "nse",
        }
    try:
        from ai_cio.services.twin_analytics import build_portfolio_preanalysis

        payload["preanalysis"] = build_portfolio_preanalysis(db, user_id)
    except Exception:
        payload["preanalysis"] = {
            "available": False,
            "note": "Portfolio pre-analysis is temporarily unavailable.",
        }
    return payload
