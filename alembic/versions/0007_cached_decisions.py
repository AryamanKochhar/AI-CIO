"""Cache DecisionResult by user + objective + input fingerprint.

Revision ID: 0007_cached_decisions
Revises: 0006_fixed_deposits
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0007_cached_decisions"
down_revision: Union[str, None] = "0006_fixed_deposits"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cached_decisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("objective", sa.String(64), nullable=False),
        sa.Column("request_key", sa.String(64), nullable=False),
        sa.Column("input_fingerprint", sa.String(64), nullable=False),
        sa.Column("result", postgresql.JSONB().with_variant(sa.JSON(), "sqlite"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("user_id", "objective", "request_key", name="uq_cached_decisions_user_obj_req"),
    )
    op.create_index("ix_cached_decisions_user_id", "cached_decisions", ["user_id"])
    op.create_index("ix_cached_decisions_objective", "cached_decisions", ["objective"])
    op.create_index("ix_cached_decisions_input_fingerprint", "cached_decisions", ["input_fingerprint"])


def downgrade() -> None:
    op.drop_index("ix_cached_decisions_input_fingerprint", table_name="cached_decisions")
    op.drop_index("ix_cached_decisions_objective", table_name="cached_decisions")
    op.drop_index("ix_cached_decisions_user_id", table_name="cached_decisions")
    op.drop_table("cached_decisions")
