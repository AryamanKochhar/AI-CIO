"""Add user journey and goal/finance fields.

Revision ID: 0002_journey
Revises: 0001_canonical
Create Date: 2026-08-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_journey"
down_revision: Union[str, None] = "0001_canonical"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("goals", sa.Column("goal_type", sa.String(64), nullable=True))
    op.add_column("goals", sa.Column("target_date", sa.String(32), nullable=True))
    op.add_column("goals", sa.Column("current_funding", sa.Numeric(), nullable=True))
    op.add_column("goals", sa.Column("priority", sa.String(32), nullable=True))
    op.add_column("goals", sa.Column("flexibility", sa.String(32), nullable=True))
    op.add_column("liabilities", sa.Column("monthly_payment", sa.Numeric(), nullable=True))
    op.create_table(
        "user_journeys",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("current_step", sa.String(32), nullable=False),
        sa.Column("finances_status", sa.String(32), nullable=False),
        sa.Column("goals_status", sa.String(32), nullable=False),
        sa.Column("portfolio_status", sa.String(32), nullable=False),
        sa.Column("decision", sa.String(32), nullable=True),
        sa.Column("decision_notes", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", name="uq_user_journeys_user_id"),
    )
    op.create_index("ix_user_journeys_user_id", "user_journeys", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_user_journeys_user_id", table_name="user_journeys")
    op.drop_table("user_journeys")
    op.drop_column("liabilities", "monthly_payment")
    op.drop_column("goals", "flexibility")
    op.drop_column("goals", "priority")
    op.drop_column("goals", "current_funding")
    op.drop_column("goals", "target_date")
    op.drop_column("goals", "goal_type")
