"""Store explicit FIRE goal assumptions independently from prose notes."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0008_fire_goal_inputs"
down_revision = "0007_cached_decisions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("goals", sa.Column("planning_inputs", postgresql.JSONB().with_variant(sa.JSON(), "sqlite"), nullable=True))


def downgrade() -> None:
    op.drop_column("goals", "planning_inputs")
