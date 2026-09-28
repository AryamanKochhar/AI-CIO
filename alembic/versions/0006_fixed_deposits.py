"""Fixed deposits: user holdings + scraped bank FD rates.

Revision ID: 0006_fixed_deposits
Revises: 0005_market_intelligence
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0006_fixed_deposits"
down_revision: Union[str, None] = "0005_market_intelligence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "fixed_deposits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("bank_name", sa.String(255), nullable=False),
        sa.Column("account_label", sa.String(255), nullable=True),
        sa.Column("principal", sa.Numeric(), nullable=False),
        sa.Column("interest_rate_pa", sa.Numeric(), nullable=True),
        sa.Column("tenure_months", sa.Integer(), nullable=True),
        sa.Column("start_date", sa.String(32), nullable=True),
        sa.Column("maturity_date", sa.String(32), nullable=True),
        sa.Column("compounding", sa.String(32), nullable=True),
        sa.Column("is_senior_citizen", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_fixed_deposits_bank_name", "fixed_deposits", ["bank_name"])

    op.create_table(
        "fd_rate_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("source_url", sa.String(512), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("as_of_note", sa.String(255), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="ok"),
        sa.Column("error", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("fd_rate_snapshots")
    op.drop_index("ix_fixed_deposits_bank_name", table_name="fixed_deposits")
    op.drop_table("fixed_deposits")
