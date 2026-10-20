"""Allow FIRE in the existing goal-type database constraint.

Keep the ORM-created test schema and migrated databases consistent. No goal
records are converted or deleted, including on downgrade.
"""
from alembic import op
import sqlalchemy as sa

revision = "0009_fire_goal_type"
down_revision = "0008_fire_goal_inputs"
branch_labels = None
depends_on = None

OLD_TYPES = "goal_type IS NULL OR goal_type IN ('emergency', 'retirement', 'education', 'home', 'vehicle', 'travel', 'wealth', 'other')"
NEW_TYPES = "goal_type IS NULL OR goal_type IN ('emergency', 'retirement', 'education', 'home', 'vehicle', 'travel', 'wealth', 'other', 'fire')"


def upgrade():
    op.drop_constraint("ck_goals_type", "goals", type_="check")
    op.create_check_constraint("ck_goals_type", "goals", NEW_TYPES)


def downgrade():
    if op.get_bind().execute(sa.text("SELECT count(*) FROM goals WHERE goal_type='fire'")).scalar_one():
        raise RuntimeError("Reclassify or remove FIRE goals explicitly before downgrading; no records were changed")
    op.drop_constraint("ck_goals_type", "goals", type_="check")
    op.create_check_constraint("ck_goals_type", "goals", OLD_TYPES)
