"""Errors for the decision orchestration layer."""

from ai_cio.services.instruments import DomainError


class OrchestrationError(DomainError):
    pass


class MissingPsychometricProfile(OrchestrationError):
    pass


class MissingPortfolio(OrchestrationError):
    pass


class MissingGoalInformation(OrchestrationError):
    pass


class InsufficientDecisionContext(OrchestrationError):
    pass


class DecisionValidationError(OrchestrationError):
    pass
