"""Human-readable profile review. Missing facts stay unknown — never filled in."""
from __future__ import annotations

from analysis import total_value
from ai_cio.psychometrics.observations import generate_observations
from ai_cio.psychometrics.polarity import DIMENSION_POLARITY
from ai_cio.services.assessments import SCORE_FIELDS, latest_profile
from ai_cio.services.finances import serialize_finances
from ai_cio.services.goals import list_goals, serialize_goal
from ai_cio.services.identity import get_user
from ai_cio.services.instruments import DomainError
from ai_cio.services.journey import get_or_create_journey, serialize_journey
from ai_cio.services.portfolio import document_count, list_holdings


def _fact(value, source: str, known_if=None):
    present = value not in (None, "", [], {}) if known_if is None else known_if
    if not present:
        return {"status": "unknown", "value": None, "source": None}
    return {"status": "known", "value": value, "source": source}


def assemble_review(db, user_id: int) -> dict:
    user = get_user(db, user_id)
    journey = get_or_create_journey(db, user_id)
    finances = serialize_finances(db, user_id)
    goals = [serialize_goal(row) for row in list_goals(db, user_id)]
    holdings = list_holdings(db, user_id)
    docs = document_count(db, user_id)

    behaviour = None
    try:
        profile = latest_profile(db, user_id)
        scores = {field: getattr(profile, field) for field in SCORE_FIELDS}
        behaviour = {
            "status": "known",
            "source": "system-derived",
            "scores": scores,
            "polarity": profile.polarity,
            "observations": generate_observations(scores),
            "profile_confidence": profile.profile_confidence,
        }
    except DomainError:
        behaviour = {"status": "unknown", "source": None, "scores": None, "observations": []}

    portfolio_total = f"{total_value(holdings):.2f}" if holdings else None
    completeness = {
        "psychometric": behaviour["status"] == "known",
        "income": finances["income"] is not None,
        "expenses": finances["expenses"] is not None,
        "liquid": finances["liquid"] is not None,
        "liabilities": bool(finances["liabilities"]) or journey.finances_status == "provided",
        "goals": bool(goals),
        "portfolio": bool(holdings),
        "finances_skipped": journey.finances_status == "skipped",
        "goals_skipped": journey.goals_status == "skipped",
        "portfolio_skipped": journey.portfolio_status == "skipped",
    }
    return {
        "user": {"id": user.id, "name": user.name, "source": "user-provided"},
        "journey": serialize_journey(journey),
        "behaviour": behaviour,
        "finances": {
            "income": _fact(finances["income"], "user-provided"),
            "expenses": _fact(finances["expenses"], "user-provided"),
            "liquid": _fact(finances["liquid"], "user-provided"),
            "cadence": finances["cadence"],
            "liabilities": _fact(finances["liabilities"], "user-provided", known_if=bool(finances["liabilities"])),
            "status": journey.finances_status,
        },
        "goals": {
            "items": goals,
            "status": "known" if goals else ("skipped" if journey.goals_status == "skipped" else "unknown"),
            "source": "user-provided" if goals else None,
        },
        "portfolio": {
            "document_count": docs,
            "holdings_count": len(holdings),
            "total_value": _fact(portfolio_total, "cas-derived", known_if=bool(holdings)),
            "holdings": [
                {
                    "amc": row["amc"],
                    "scheme_name": row["scheme_name"],
                    "valuation": f"{row['valuation']:.2f}",
                    "source_page": row["source_page"],
                    "source": "cas-derived",
                }
                for row in holdings[:12]
            ],
            "status": journey.portfolio_status,
        },
        "completeness": completeness,
        "dimension_labels": {
            name: spec["higher_means"] for name, spec in DIMENSION_POLARITY.items()
        },
    }
