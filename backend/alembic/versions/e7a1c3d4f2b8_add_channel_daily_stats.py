"""add channel_daily_stats table for real historical chart data

Revision ID: e7a1c3d4f2b8
Revises: d5e8f2a3b9c1
Create Date: 2026-03-11

"""
from alembic import op
import sqlalchemy as sa

revision = "e7a1c3d4f2b8"
down_revision = "d5e8f2a3b9c1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "channel_daily_stats",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("channel_id", sa.Uuid(), sa.ForeignKey("channels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        # core metrics
        sa.Column("views", sa.Integer(), nullable=True),
        sa.Column("estimated_minutes_watched", sa.Float(), nullable=True),
        sa.Column("average_view_duration_seconds", sa.Float(), nullable=True),
        sa.Column("likes", sa.Integer(), nullable=True),
        sa.Column("comments", sa.Integer(), nullable=True),
        sa.Column("subscribers_gained", sa.Integer(), nullable=True),
        sa.Column("subscribers_lost", sa.Integer(), nullable=True),
        # reach — available from ~2018, stored as 0–1 fraction
        sa.Column("impressions", sa.Integer(), nullable=True),
        sa.Column("click_through_rate", sa.Float(), nullable=True),
        # revenue — requires monetary scope
        sa.Column("estimated_revenue", sa.Float(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_unique_constraint(
        "uq_channel_daily_stats_channel_date",
        "channel_daily_stats",
        ["channel_id", "date"],
    )
    op.create_index(
        "ix_channel_daily_stats_channel_date",
        "channel_daily_stats",
        ["channel_id", "date"],
    )


def downgrade() -> None:
    op.drop_table("channel_daily_stats")
