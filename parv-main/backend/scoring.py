"""Behavioral scoring engine for psychometric assessments."""
from typing import List, Dict, Tuple
import math
from sqlalchemy.orm import Session
from backend.models import Response, AssessmentSession, Profile
from datetime import datetime


class BehavioralScorer:
    """Calculates behavioral dimension scores from assessment responses."""

    # Map question IDs to their dimensions
    # This will be populated from the questions.json
    DIMENSION_QUESTIONS = {
        "risk_tolerance": ["Q001", "Q002", "Q015"],
        "loss_aversion": ["Q003", "Q004", "Q016"],
        "anchoring": ["Q005", "Q006", "Q018"],
        "recency_bias": ["Q007", "Q008"],
        "herding": ["Q009", "Q010", "Q017"],
        "overconfidence": ["Q011", "Q012"],
        "decision_stability": ["Q013", "Q014"],
    }

    @staticmethod
    def calculate_profile(session_id: int, db: Session) -> Dict[str, float]:
        """
        Calculate behavioral profile for a completed assessment session.

        Args:
            session_id: The assessment session ID
            db: Database session

        Returns:
            Dictionary with all calculated scores and metrics
        """
        # Fetch all responses for this session
        responses: List[Response] = db.query(Response).filter(
            Response.session_id == session_id
        ).all()

        if not responses:
            raise ValueError(f"No responses found for session {session_id}")

        # Calculate dimension scores
        dimension_scores = BehavioralScorer._calculate_dimension_scores(responses)

        # Calculate aggregate metrics
        avg_confidence = BehavioralScorer._calculate_average_confidence(responses)
        avg_response_time = BehavioralScorer._calculate_average_response_time(responses)
        profile_confidence = BehavioralScorer._calculate_profile_confidence(
            responses, avg_confidence
        )

        return {
            "risk_score": dimension_scores["risk_tolerance"],
            "loss_aversion_score": dimension_scores["loss_aversion"],
            "anchoring_score": dimension_scores["anchoring"],
            "recency_bias_score": dimension_scores["recency_bias"],
            "herding_score": dimension_scores["herding"],
            "overconfidence_score": dimension_scores["overconfidence"],
            "decision_stability_score": dimension_scores["decision_stability"],
            "average_confidence": avg_confidence,
            "average_response_time_ms": avg_response_time,
            "profile_confidence": profile_confidence,
        }

    @staticmethod
    def _calculate_dimension_scores(responses: List[Response]) -> Dict[str, float]:
        """Calculate normalized score (0-100) for each behavioral dimension."""
        dimension_scores = {}

        for dimension, question_ids in BehavioralScorer.DIMENSION_QUESTIONS.items():
            # Get responses for this dimension
            dimension_responses = [r for r in responses if r.question_id in question_ids]

            if not dimension_responses:
                dimension_scores[dimension] = 50.0  # Default middle score
                continue

            # Calculate average score from response values
            total_score = sum(int(r.answer) for r in dimension_responses if r.answer.isdigit())
            
            # Handle non-numeric answers (A, B, C, D)
            for r in dimension_responses:
                if not r.answer.isdigit():
                    # This is handled through the question options
                    # The score is stored when the answer is submitted
                    # For now, we'll treat non-numeric answers as having their face value
                    try:
                        total_score += int(r.answer)
                    except ValueError:
                        # Map A, B, C, D to 1, 2, 3, 4
                        answer_map = {"A": 1, "B": 2, "C": 3, "D": 4}
                        total_score += answer_map.get(r.answer, 3)

            avg_score = total_score / len(dimension_responses)

            # Normalize to 0-100 scale (assuming raw scores are typically 1-5)
            normalized_score = ((avg_score - 1) / 4) * 100
            normalized_score = max(0, min(100, normalized_score))  # Clamp to 0-100

            dimension_scores[dimension] = round(normalized_score, 1)

        return dimension_scores

    @staticmethod
    def _calculate_average_confidence(responses: List[Response]) -> float:
        """Calculate average confidence (0-100)."""
        if not responses:
            return 0.0
        avg_conf = sum(r.confidence for r in responses) / len(responses)
        return round(avg_conf, 1)

    @staticmethod
    def _calculate_average_response_time(responses: List[Response]) -> float:
        """Calculate average response time in milliseconds."""
        if not responses:
            return 0.0
        avg_time = sum(r.response_time_ms for r in responses) / len(responses)
        return round(avg_time, 1)

    @staticmethod
    def _calculate_profile_confidence(
        responses: List[Response], avg_confidence: float
    ) -> float:
        """
        Calculate reliability of the profile from confidence and timing signals.

        The timing score peaks around 20 seconds per question. Very fast answers
        can indicate guessing, while very slow answers can indicate uncertainty.
        """
        if not responses:
            return 0.0

        confidence_signal = max(0.0, min(100.0, avg_confidence))
        timing_scores = []
        confidence_values = [r.confidence for r in responses]

        for response in responses:
            seconds = max(response.response_time_ms, 0) / 1000
            timing_scores.append(
                100 * math.exp(-((seconds - 20) / 20) ** 2)
            )

        timing_signal = sum(timing_scores) / len(timing_scores)

        mean_confidence = sum(confidence_values) / len(confidence_values)
        variance = sum(
            (value - mean_confidence) ** 2 for value in confidence_values
        ) / len(confidence_values)
        consistency_signal = max(0.0, 100.0 - math.sqrt(variance))

        reliability = (
            confidence_signal * 0.55
            + timing_signal * 0.25
            + consistency_signal * 0.20
        )
        return round(max(0.0, min(100.0, reliability)), 1)

    @staticmethod
    def generate_observations(scores: Dict[str, float]) -> List[str]:
        """
        Generate textual observations based on calculated scores.

        Args:
            scores: Dictionary with all dimension scores

        Returns:
            List of observation strings
        """
        observations = []

        # Risk tolerance interpretation
        risk_score = scores["risk_score"]
        if risk_score >= 70:
            observations.append(
                f"Responses indicate relatively high willingness to accept investment risk ({risk_score:.0f}/100)."
            )
        elif risk_score >= 40:
            observations.append(
                f"Responses indicate moderate risk tolerance with some caution ({risk_score:.0f}/100)."
            )
        else:
            observations.append(
                f"Responses indicate preference for stability over higher-risk opportunities ({risk_score:.0f}/100)."
            )

        # Loss aversion interpretation
        loss_aversion = scores["loss_aversion_score"]
        if loss_aversion >= 70:
            observations.append(
                f"Responses indicate relatively high sensitivity to potential losses ({loss_aversion:.0f}/100). "
                "This may lead to defensive positioning."
            )
        elif loss_aversion < 40:
            observations.append(
                f"Responses indicate lower concern about losses ({loss_aversion:.0f}/100). "
                "This may enable opportunistic buying during downturns."
            )

        # Anchoring bias interpretation
        anchoring = scores["anchoring_score"]
        if anchoring >= 70:
            observations.append(
                f"Responses suggest possible anchoring to previous prices or reference points ({anchoring:.0f}/100). "
                "Consider evaluating positions based on current fundamentals rather than historical prices."
            )

        # Recency bias interpretation
        recency = scores["recency_bias_score"]
        if recency >= 70:
            observations.append(
                f"Responses suggest recent performance may disproportionately influence decisions ({recency:.0f}/100). "
                "This could lead to overweighting recent trends."
            )
        elif recency < 40:
            observations.append(
                f"Responses suggest resistance to following recent market trends ({recency:.0f}/100). "
                "This may prevent chasing bubbles but could also miss momentum opportunities."
            )

        # Herding behavior interpretation
        herding = scores["herding_score"]
        if herding >= 70:
            observations.append(
                f"Responses suggest possible tendency to follow crowd behavior ({herding:.0f}/100). "
                "Independent research may help counter group dynamics."
            )

        # Overconfidence interpretation
        overconfidence = scores["overconfidence_score"]
        if overconfidence >= 70:
            observations.append(
                f"Responses suggest higher confidence in market-beating ability ({overconfidence:.0f}/100). "
                "Consider the challenges of consistent outperformance."
            )
        elif overconfidence < 30:
            observations.append(
                f"Responses suggest cautious view of personal investment skill ({overconfidence:.0f}/100). "
                "This humility may lead to index-based or diversified strategies."
            )

        # Decision stability interpretation
        decision_stability = scores["decision_stability_score"]
        if decision_stability >= 70:
            observations.append(
                f"Responses indicate tendency to maintain conviction in decisions ({decision_stability:.0f}/100). "
                "This can support long-term strategies but requires checking for confirmation bias."
            )
        elif decision_stability < 40:
            observations.append(
                f"Responses indicate adaptability to new information ({decision_stability:.0f}/100). "
                "This flexibility is valuable but ensure changes are based on substance, not noise."
            )

        return observations
