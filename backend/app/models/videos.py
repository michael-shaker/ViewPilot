import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    channel_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, sa.ForeignKey("channels.id", ondelete="CASCADE"))
    youtube_video_id: Mapped[str] = mapped_column(sa.String(255), unique=True)
    title: Mapped[str] = mapped_column(sa.Text)
    description: Mapped[str | None] = mapped_column(sa.Text)
    tags: Mapped[list | None] = mapped_column(ARRAY(sa.Text))
    category_id: Mapped[str | None] = mapped_column(sa.String(10))
    duration_seconds: Mapped[int | None] = mapped_column(sa.Integer)
    published_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    thumbnail_url: Mapped[str | None] = mapped_column(sa.Text)
    default_language: Mapped[str | None] = mapped_column(sa.String(10))
    is_short: Mapped[bool] = mapped_column(sa.Boolean, default=False)
    playlist_ids: Mapped[list | None] = mapped_column(ARRAY(sa.Text))
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class VideoComment(Base):
    __tablename__ = "video_comments"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    video_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, sa.ForeignKey("videos.id", ondelete="CASCADE"))
    youtube_comment_id: Mapped[str] = mapped_column(sa.String(255), unique=True)
    parent_youtube_id: Mapped[str | None] = mapped_column(sa.String(255))  # null = top-level comment
    author_name: Mapped[str] = mapped_column(sa.Text)
    author_image_url: Mapped[str | None] = mapped_column(sa.Text)
    author_channel_url: Mapped[str | None] = mapped_column(sa.Text)
    author_channel_id: Mapped[str | None] = mapped_column(sa.String(255))
    text: Mapped[str] = mapped_column(sa.Text)
    like_count: Mapped[int] = mapped_column(sa.Integer, default=0)
    reply_count: Mapped[int] = mapped_column(sa.Integer, default=0)  # only set on top-level
    is_reply: Mapped[bool] = mapped_column(sa.Boolean, default=False)
    published_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    updated_at_youtube: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)
