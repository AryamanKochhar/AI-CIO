"""Canonical AI-CIO schema: identity, psychometrics, documents, portfolio, stubs.

Revision ID: 0001_canonical
Revises:
Create Date: 2026-08-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_canonical"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "instruments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("version", name="uq_instruments_version"),
    )

    op.create_table(
        "assessment_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("instrument_id", sa.Integer(), sa.ForeignKey("instruments.id"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('in_progress', 'completed', 'abandoned')",
            name="ck_assessment_sessions_status",
        ),
    )
    op.create_index("ix_assessment_sessions_user_id", "assessment_sessions", ["user_id"])
    op.create_index("ix_assessment_sessions_instrument_id", "assessment_sessions", ["instrument_id"])

    op.create_table(
        "assessment_responses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("assessment_sessions.id"), nullable=False),
        sa.Column("question_id", sa.String(16), nullable=False),
        sa.Column("answer_id", sa.String(32), nullable=False),
        sa.Column("score_applied", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Integer(), nullable=False),
        sa.Column("response_time_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("session_id", "question_id", name="uq_assessment_responses_session_question"),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 100",
            name="ck_assessment_responses_confidence",
        ),
    )
    op.create_index("ix_assessment_responses_session_id", "assessment_responses", ["session_id"])

    op.create_table(
        "behavioral_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("assessment_sessions.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("instrument_id", sa.Integer(), sa.ForeignKey("instruments.id"), nullable=False),
        sa.Column("risk_score", sa.Float(), nullable=False),
        sa.Column("loss_aversion_score", sa.Float(), nullable=False),
        sa.Column("anchoring_score", sa.Float(), nullable=False),
        sa.Column("recency_bias_score", sa.Float(), nullable=False),
        sa.Column("herding_score", sa.Float(), nullable=False),
        sa.Column("overconfidence_score", sa.Float(), nullable=False),
        sa.Column("decision_stability_score", sa.Float(), nullable=False),
        sa.Column("average_confidence", sa.Float(), nullable=False),
        sa.Column("average_response_time_ms", sa.Float(), nullable=False),
        sa.Column("profile_confidence", sa.Float(), nullable=False),
        sa.Column("polarity", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("session_id", name="uq_behavioral_profiles_session_id"),
    )
    op.create_index("ix_behavioral_profiles_user_id", "behavioral_profiles", ["user_id"])

    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("parser_version", sa.String(64), nullable=True),
        sa.Column("checksum", sa.String(128), nullable=True),
        sa.Column("warning_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_documents_user_id", "documents", ["user_id"])

    op.create_table(
        "source_pages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("page", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.UniqueConstraint("document_id", "page", name="uq_source_pages_document_page"),
    )
    op.create_index("ix_source_pages_document_id", "source_pages", ["document_id"])
    op.create_index("ix_source_pages_user_id", "source_pages", ["user_id"])

    op.create_table(
        "funds",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("amc", sa.Text(), nullable=False),
        sa.Column("folio", sa.Text(), nullable=False),
        sa.Column("scheme_name", sa.Text(), nullable=False),
        sa.Column("isin", sa.Text(), nullable=True),
        sa.UniqueConstraint(
            "document_id", "amc", "folio", "scheme_name", "isin",
            name="uq_funds_document_identity",
        ),
    )
    op.create_index("ix_funds_user_id", "funds", ["user_id"])
    op.create_index("ix_funds_document_id", "funds", ["document_id"])

    op.create_table(
        "holdings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("fund_id", sa.Integer(), sa.ForeignKey("funds.id"), nullable=False),
        sa.Column("opening_units", sa.Numeric(), nullable=True),
        sa.Column("closing_units", sa.Numeric(), nullable=True),
        sa.Column("nav", sa.Numeric(), nullable=True),
        sa.Column("valuation", sa.Numeric(), nullable=True),
        sa.Column("valuation_date", sa.String(32), nullable=True),
        sa.Column("source_page", sa.Integer(), nullable=False),
    )
    op.create_index("ix_holdings_user_id", "holdings", ["user_id"])
    op.create_index("ix_holdings_document_id", "holdings", ["document_id"])
    op.create_index("ix_holdings_fund_id", "holdings", ["fund_id"])

    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("fund_id", sa.Integer(), sa.ForeignKey("funds.id"), nullable=False),
        sa.Column("date", sa.String(32), nullable=True),
        sa.Column("transaction_type", sa.String(64), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("amount", sa.Numeric(), nullable=True),
        sa.Column("units", sa.Numeric(), nullable=True),
        sa.Column("nav", sa.Numeric(), nullable=True),
        sa.Column("unit_balance", sa.Numeric(), nullable=True),
        sa.Column("source_page", sa.Integer(), nullable=False),
    )
    op.create_index("ix_transactions_user_id", "transactions", ["user_id"])
    op.create_index("ix_transactions_document_id", "transactions", ["document_id"])
    op.create_index("ix_transactions_fund_id", "transactions", ["fund_id"])

    op.create_table(
        "goals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("target_amount", sa.Numeric(), nullable=True),
        sa.Column("horizon_years", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_goals_user_id", "goals", ["user_id"])

    op.create_table(
        "cashflows",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("kind", sa.String(32), nullable=True),
        sa.Column("amount", sa.Numeric(), nullable=True),
        sa.Column("cadence", sa.String(32), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_cashflows_user_id", "cashflows", ["user_id"])

    op.create_table(
        "liabilities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("balance", sa.Numeric(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_liabilities_user_id", "liabilities", ["user_id"])

    op.create_table(
        "constraints",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("kind", sa.String(64), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_constraints_user_id", "constraints", ["user_id"])


def downgrade() -> None:
    for table in (
        "constraints",
        "liabilities",
        "cashflows",
        "goals",
        "transactions",
        "holdings",
        "funds",
        "source_pages",
        "documents",
        "behavioral_profiles",
        "assessment_responses",
        "assessment_sessions",
        "instruments",
        "users",
    ):
        op.drop_table(table)
