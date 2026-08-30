"""Add MVP auth fields and broaden document kinds for NSDL/CDSL.

Revision ID: 0003_auth_documents
Revises: 0002_journey
Create Date: 2026-08-30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003_auth_documents"
down_revision: Union[str, None] = "0002_journey"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # MVP auth: email + password hash. Do not store plaintext.
    op.add_column("users", sa.Column("email", sa.String(320), nullable=True))
    op.add_column("users", sa.Column("password_hash", sa.String(255), nullable=True))
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # Documents: support more kinds and explicit processing / validation status.
    op.alter_column("documents", "kind", server_default=None)
    op.add_column("documents", sa.Column("status", sa.String(32), nullable=False, server_default="pending"))
    op.add_column("documents", sa.Column("validation_status", sa.String(32), nullable=True))
    op.create_check_constraint(
        "ck_documents_status",
        "documents",
        "status IN ('pending', 'processing', 'extracted', 'needs_review', 'failed')",
    )
    op.create_check_constraint(
        "ck_documents_validation_status",
        "documents",
        "validation_status IS NULL OR validation_status IN ('unvalidated', 'valid', 'partial', 'invalid')",
    )

    # Goals: extend allowed types used by the UI and tests.
    op.create_check_constraint(
        "ck_goals_type",
        "goals",
        "goal_type IS NULL OR goal_type IN ('emergency', 'retirement', 'education', 'home', 'vehicle', 'travel', 'wealth', 'other')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_goals_type", "goals", type_="check")
    op.drop_constraint("ck_documents_validation_status", "documents", type_="check")
    op.drop_constraint("ck_documents_status", "documents", type_="check")
    op.drop_column("documents", "validation_status")
    op.drop_column("documents", "status")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_column("users", "password_hash")
    op.drop_column("users", "email")
