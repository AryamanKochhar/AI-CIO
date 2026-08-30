"""Dimension polarity verified against instruments/v1.0.json (parv questions.json).

Polarity is derived from each option's `score` field, not from answer ids.

Risk tolerance (Q001, Q002, Q015):
  Higher option scores are assigned to greater comfort with volatility and
  temporary losses. Q002 is reverse-scored in JSON (preferring steady returns
  maps to lower scores).

Loss aversion (Q003, Q004, Q016):
  Higher option scores are assigned to holding/buying in drawdowns, not being
  kept up by losses, and preferring riskier payoffs. High score = lower /
  more adaptive loss sensitivity.

Anchoring (Q005, Q006, Q018):
  Higher option scores are assigned to ignoring original price, not using
  prior benchmarks, and being able to exit long-held underperformers.
  High score = less anchoring.

Recency bias (Q007, Q008):
  Higher option scores are assigned to not overweighting recent performance.
  High score = less recency bias.

Herding (Q009, Q010, Q017):
  Higher option scores are assigned to independent research and not following
  crowds or popular commentators. High score = less herding.

Overconfidence (Q011, Q012):
  Higher option scores are assigned to disagreeing that one can consistently
  beat the market or is better than average. High score = less overconfidence.

Decision stability (Q013, Q014):
  Higher option scores are assigned to maintaining conviction and not
  frequently second-guessing. High score = greater decision stability.
"""

from __future__ import annotations

from typing import TypedDict


class DimensionPolarity(TypedDict):
    dimension: str
    profile_key: str
    higher_means: str
    lower_means: str
    question_ids: tuple[str, ...]


DIMENSION_POLARITY: dict[str, DimensionPolarity] = {
    "risk_tolerance": {
        "dimension": "risk_tolerance",
        "profile_key": "risk_score",
        "higher_means": "greater willingness to accept investment risk",
        "lower_means": "greater preference for stability over higher-risk opportunities",
        "question_ids": ("Q001", "Q002", "Q015"),
    },
    "loss_aversion": {
        "dimension": "loss_aversion",
        "profile_key": "loss_aversion_score",
        "higher_means": "lower / more adaptive sensitivity to investment losses",
        "lower_means": "greater sensitivity to investment losses",
        "question_ids": ("Q003", "Q004", "Q016"),
    },
    "anchoring": {
        "dimension": "anchoring",
        "profile_key": "anchoring_score",
        "higher_means": "less anchoring to prior prices or reference points",
        "lower_means": "greater reliance on prior prices or reference points",
        "question_ids": ("Q005", "Q006", "Q018"),
    },
    "recency_bias": {
        "dimension": "recency_bias",
        "profile_key": "recency_bias_score",
        "higher_means": "less overweighting of recent performance",
        "lower_means": "greater influence of recent performance on decisions",
        "question_ids": ("Q007", "Q008"),
    },
    "herding": {
        "dimension": "herding",
        "profile_key": "herding_score",
        "higher_means": "more independent decision-making / less crowd-following",
        "lower_means": "greater tendency to follow crowd or popular commentary",
        "question_ids": ("Q009", "Q010", "Q017"),
    },
    "overconfidence": {
        "dimension": "overconfidence",
        "profile_key": "overconfidence_score",
        "higher_means": "more calibrated view of personal investment skill",
        "lower_means": "greater confidence in market-beating ability",
        "question_ids": ("Q011", "Q012"),
    },
    "decision_stability": {
        "dimension": "decision_stability",
        "profile_key": "decision_stability_score",
        "higher_means": "greater decision stability / maintaining conviction",
        "lower_means": "greater tendency to revise or second-guess decisions",
        "question_ids": ("Q013", "Q014"),
    },
}

PROFILE_KEY_TO_DIMENSION = {
    spec["profile_key"]: name for name, spec in DIMENSION_POLARITY.items()
}


def polarity_payload() -> dict[str, dict[str, str]]:
    """JSON stored on each behavioral profile so downstream readers cannot invert scores."""
    return {
        name: {
            "profile_key": spec["profile_key"],
            "higher_means": spec["higher_means"],
            "lower_means": spec["lower_means"],
            "question_ids": ",".join(spec["question_ids"]),
        }
        for name, spec in DIMENSION_POLARITY.items()
    }
