"""add video_comments table

Revision ID: d5e8f2a3b9c1
Revises: b3c8d1e2f4a5
Create Date: 2026-02-28

"""
from alembic import op
import sqlalchemy as sa

revision = "d5e8f2a3b9c1"
down_revision = "b3c8d1e2f4a5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "video_comments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("video_id", sa.Uuid(), sa.ForeignKey("videos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("youtube_comment_id", sa.String(255), nullable=False, unique=True),
        sa.Column("parent_youtube_id", sa.String(255), nullable=True),  # null = top-level
        sa.Column("author_name", sa.Text(), nullable=False),
        sa.Column("author_image_url", sa.Text(), nullable=True),
        sa.Column("author_channel_url", sa.Text(), nullable=True),
        sa.Column("author_channel_id", sa.String(255), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("like_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reply_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_reply", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at_youtube", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_video_comments_video_id", "video_comments", ["video_id"])
    op.create_index("ix_video_comments_parent_youtube_id", "video_comments", ["parent_youtube_id"])
    op.create_index("ix_video_comments_like_count", "video_comments", ["like_count"])


def downgrade() -> None:
    op.drop_table("video_comments")
