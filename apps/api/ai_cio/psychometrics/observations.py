"""Plain-language observations that follow instrument polarity.

High scores on bias-labelled dimensions mean more adaptive / less biased
behaviour, as established by instruments/v1.0.json option scores.
"""
from __future__ import annotations

from ai_cio.psychometrics.polarity import DIMENSION_POLARITY, PROFILE_KEY_TO_DIMENSION

HIGH = 70.0
LOW = 40.0


def generate_observations(scores: dict[str, float]) -> list[str]:
    observations: list[str] = []
    for profile_key, dimension in PROFILE_KEY_TO_DIMENSION.items():
        if profile_key not in scores:
            raise KeyError(f"Missing score for {profile_key}")
        value = scores[profile_key]
        polarity = DIMENSION_POLARITY[dimension]
        observations.extend(_for_dimension(dimension, value, polarity["higher_means"], polarity["lower_means"]))
    return observations


def _for_dimension(dimension: str, score: float, higher_means: str, lower_means: str) -> list[str]:
    label = dimension.replace("_", " ")
    if dimension == "risk_tolerance":
        if score >= HIGH:
            return [
                f"Responses indicate relatively high willingness to accept investment risk ({score:.0f}/100)."
            ]
        if score >= LOW:
            return [
                f"Responses indicate moderate risk tolerance with some caution ({score:.0f}/100)."
            ]
        return [
            f"Responses indicate preference for stability over higher-risk opportunities ({score:.0f}/100)."
        ]

    if score >= HIGH:
        return [
            f"Responses on {label} indicate {higher_means} ({score:.0f}/100)."
        ]
    if score < LOW:
        return [
            f"Responses on {label} indicate {lower_means} ({score:.0f}/100)."
        ]
    return []
