"""Market intelligence: indices, snapshots, securities, opportunities, alerts.

Revision ID: 0005_market_intelligence
Revises: 0004_cdsl_portfolio
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0005_market_intelligence"
down_revision: Union[str, None] = "0004_cdsl_portfolio"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "market_indices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(32), nullable=False, server_default="nse"),
        sa.Column("symbol", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("provider", "symbol", name="uq_market_indices_provider_symbol"),
    )
    op.create_index("ix_market_indices_category", "market_indices", ["category"])

    op.create_table(
        "market_index_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("index_id", sa.Integer(), sa.ForeignKey("market_indices.id"), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_value", sa.Numeric(), nullable=True),
        sa.Column("close_value", sa.Numeric(), nullable=True),
        sa.Column("open_value", sa.Numeric(), nullable=True),
        sa.Column("high_value", sa.Numeric(), nullable=True),
        sa.Column("low_value", sa.Numeric(), nullable=True),
        sa.Column("percentage_change", sa.Numeric(), nullable=True),
        sa.Column("year_high", sa.Numeric(), nullable=True),
        sa.Column("year_low", sa.Numeric(), nullable=True),
        sa.Column("source", sa.String(64), nullable=False, server_default="nse"),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_stale", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.UniqueConstraint("index_id", "timestamp", name="uq_market_index_snapshots_index_ts"),
    )
    op.create_index("ix_market_index_snapshots_index_ts", "market_index_snapshots", ["index_id", "timestamp"])
    op.create_index("ix_market_index_snapshots_timestamp", "market_index_snapshots", ["timestamp"])

    op.create_table(
        "securities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("isin", sa.String(16), nullable=True),
        sa.Column("symbol", sa.String(32), nullable=True),
        sa.Column("name", sa.String(512), nullable=True),
        sa.Column("exchange", sa.String(16), nullable=False, server_default="NSE"),
        sa.Column("asset_class", sa.String(32), nullable=False, server_default="equity"),
        sa.Column("sector_index_code", sa.String(64), nullable=True),
        sa.Column("sector_name", sa.String(128), nullable=True),
        sa.Column("classification_source", sa.String(64), nullable=True),
        sa.Column("classified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_securities_isin", "securities", ["isin"], unique=True)
    op.create_index("ix_securities_symbol", "securities", ["symbol"])

    op.create_table(
        "market_opportunities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("type", sa.String(64), nullable=False),
        sa.Column("sector_index_code", sa.String(64), nullable=True),
        sa.Column("sector_name", sa.String(128), nullable=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("market_snapshot_id", sa.Integer(), sa.ForeignKey("market_index_snapshots.id"), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending_analysis"),
        sa.Column("severity", sa.String(32), nullable=False, server_default="information"),
        sa.Column("reason_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_market_opportunities_user_detected", "market_opportunities", ["user_id", "detected_at"])

    op.create_table(
        "market_opportunity_analyses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("opportunity_id", sa.Integer(), sa.ForeignKey("market_opportunities.id"), nullable=False, index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("twin_as_of", sa.DateTime(timezone=True), nullable=True),
        sa.Column("model", sa.String(128), nullable=True),
        sa.Column("prompt_version", sa.String(32), nullable=True),
        sa.Column("analysis_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("knowledge_refs", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("confidence", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "user_alerts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("opportunity_analysis_id", sa.Integer(), sa.ForeignKey("market_opportunity_analyses.id"), nullable=True),
        sa.Column("channel", sa.String(32), nullable=False, server_default="email"),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "notification_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("alert_id", sa.Integer(), sa.ForeignKey("user_alerts.id"), nullable=False, index=True),
        sa.Column("channel", sa.String(32), nullable=False),
        sa.Column("recipient", sa.String(320), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("provider_message_id", sa.String(255), nullable=True),
        sa.Column("subject", sa.String(512), nullable=True),
        sa.Column("body_preview", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("notification_deliveries")
    op.drop_table("user_alerts")
    op.drop_table("market_opportunity_analyses")
    op.drop_table("market_opportunities")
    op.drop_index("ix_securities_symbol", table_name="securities")
    op.drop_index("ix_securities_isin", table_name="securities")
    op.drop_table("securities")
    op.drop_index("ix_market_index_snapshots_timestamp", table_name="market_index_snapshots")
    op.drop_index("ix_market_index_snapshots_index_ts", table_name="market_index_snapshots")
    op.drop_table("market_index_snapshots")
    op.drop_index("ix_market_indices_category", table_name="market_indices")
    op.drop_table("market_indices")
