"""Extend portfolio holdings for CDSL CAS metadata and snapshots.

Revision ID: 0004_cdsl_portfolio
Revises: 0003_auth_documents
Create Date: 2026-08-30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0004_cdsl_portfolio"
down_revision: Union[str, None] = "0003_auth_documents"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.create_index("ix_documents_checksum", "documents", ["user_id", "checksum"], unique=False)

    op.add_column("holdings", sa.Column("asset_class", sa.String(32), nullable=True))
    op.add_column("holdings", sa.Column("invested_amount", sa.Numeric(), nullable=True))
    op.add_column("holdings", sa.Column("unrealised_pl", sa.Numeric(), nullable=True))
    op.add_column("holdings", sa.Column("unrealised_pl_pct", sa.Numeric(), nullable=True))

    op.create_table(
        "portfolio_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id"), nullable=False, index=True),
        sa.Column("month_year", sa.String(32), nullable=False),
        sa.Column("valuation", sa.Numeric(), nullable=False),
        sa.Column("change_amount", sa.Numeric(), nullable=True),
        sa.Column("change_pct", sa.Numeric(), nullable=True),
        sa.UniqueConstraint("document_id", "month_year", name="uq_portfolio_snapshots_document_month"),
    )


def downgrade() -> None:
    op.drop_table("portfolio_snapshots")
    op.drop_column("holdings", "unrealised_pl_pct")
    op.drop_column("holdings", "unrealised_pl")
    op.drop_column("holdings", "invested_amount")
    op.drop_column("holdings", "asset_class")
    op.drop_index("ix_documents_checksum", table_name="documents")
    op.drop_column("documents", "metadata_json")
