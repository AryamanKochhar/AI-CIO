"""Plain decision inputs: database sessions never enter parallel specialist tasks."""
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DecisionSnapshot:
    twin: dict[str, Any]
    holdings: list[dict] = field(default_factory=list)
    transactions: list[dict] = field(default_factory=list)
    fixed_deposits: list[dict] = field(default_factory=list)
    decision_snapshot: bool = True
