"""Connect orchestration to existing user, market, and knowledge services."""

from __future__ import annotations

from sqlalchemy.orm import Session

from ai_cio.services import market_context as market_context_svc
from ai_cio.services import twin as twin_svc
from ai_cio.services.identity import get_user
from ai_cio.services.knowledge_retriever import retrieve_knowledge
from domain.decision.contracts import DecisionObjective, Evidence


class SessionTwinProvider:
    def __init__(self, db: Session) -> None:
        self._db = db

    def load_twin(self, user_id: int) -> dict:
        get_user(self._db, user_id)
        return twin_svc.assemble_twin(self._db, user_id)


class SessionMarketProvider:
    def __init__(self, db: Session) -> None:
        self._db = db

    def load_market_context(self, user_id: int) -> dict:
        return market_context_svc.build_market_context(self._db, user_id)


class SessionKnowledgeProvider:
    def resolve(self, *, objective: DecisionObjective, topics: list[str]) -> list[Evidence]:
        refs = retrieve_knowledge(topics=topics, limit=5)
        return [
            Evidence(
                source=ref.get("source", "knowledge"),
                section=ref.get("section", objective.value),
                reference=ref.get("reference", ""),
                content=ref.get("text", ""),
                relevance=ref.get("section", ""),
            )
            for ref in refs
            if ref.get("reference")
        ]
