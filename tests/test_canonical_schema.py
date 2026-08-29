"""Schema contract tests. Do not require a running Postgres instance."""
from sqlalchemy import Float, Numeric

from ai_cio.db.models import (
    AssessmentResponse,
    AssessmentSession,
    BehavioralProfile,
    Cashflow,
    Constraint,
    Document,
    Fund,
    Goal,
    Holding,
    Instrument,
    Liability,
    SourcePage,
    Transaction,
    User,
    UserJourney,
)
from ai_cio.db.base import Base


EXPECTED_TABLES = {
    "users",
    "instruments",
    "assessment_sessions",
    "assessment_responses",
    "behavioral_profiles",
    "documents",
    "source_pages",
    "funds",
    "holdings",
    "transactions",
    "goals",
    "cashflows",
    "liabilities",
    "user_journeys",
}

MONEY_COLUMNS = {
    Holding: ("opening_units", "closing_units", "nav", "valuation"),
    Transaction: ("amount", "units", "nav", "unit_balance"),
    Goal: ("target_amount", "current_funding"),
    Cashflow: ("amount",),
    Liability: ("balance", "monthly_payment"),
}


def test_canonical_tables_are_registered():
    assert EXPECTED_TABLES <= set(Base.metadata.tables)


def test_portfolio_money_columns_are_numeric_not_float():
    for model, names in MONEY_COLUMNS.items():
        for name in names:
            column = model.__table__.c[name]
            assert isinstance(column.type, Numeric), f"{model.__tablename__}.{name} must be Numeric"
            assert not isinstance(column.type, Float)


def test_score_applied_is_separate_from_answer_id():
    columns = AssessmentResponse.__table__.c
    assert "answer_id" in columns
    assert "score_applied" in columns
    assert columns["answer_id"].name != columns["score_applied"].name


def test_portfolio_rows_carry_user_and_document():
    for model in (Fund, Holding, Transaction, SourcePage, Document):
        assert "user_id" in model.__table__.c
    for model in (Fund, Holding, Transaction, SourcePage):
        assert "document_id" in model.__table__.c


def test_assessment_rows_carry_user_and_session():
    assert "user_id" in AssessmentSession.__table__.c
    assert "instrument_id" in AssessmentSession.__table__.c
    assert "session_id" in AssessmentResponse.__table__.c
    assert "user_id" in BehavioralProfile.__table__.c
    assert "polarity" in BehavioralProfile.__table__.c


def test_identity_and_instrument_tables_exist():
    assert User.__tablename__ == "users"
    assert Instrument.__tablename__ == "instruments"
    assert Constraint.__tablename__ == "constraints"
    assert UserJourney.__tablename__ == "user_journeys"
