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
from ai_cio.services.portfolio import document_count, list_holdings


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

    return {
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
            "total_value": {"value": f"{portfolio_value:.2f}" if portfolio_value is not None else None, "source": "cas-derived" if holdings else None, "known": bool(holdings)},
            "holdings": [
                {
                    "amc": row["amc"],
                    "scheme_name": row["scheme_name"],
                    "isin": row.get("isin"),
                    "closing_units": f"{row['closing_units']:.4f}",
                    "nav": f"{row['nav']:.2f}",
                    "valuation": f"{row['valuation']:.2f}",
                    "valuation_date": row.get("valuation_date"),
                    "source_page": row["source_page"],
                    "source": "cas-derived",
                    "document_id": row["document_id"],
                }
                for row in holdings[:12]
            ],
        },
        "goals": {
            "items": goal_items,
            "source": "user-provided",
            "known": bool(goal_items),
        },
        "completeness": completeness,
        "dimension_labels": {
            name: spec["higher_means"] for name, spec in DIMENSION_POLARITY.items()
        },
        "ready_for_analysis": all(
            completeness[key] for key in ("psychometric", "income", "expenses", "liquid", "goals", "portfolio")
        ),
    }
