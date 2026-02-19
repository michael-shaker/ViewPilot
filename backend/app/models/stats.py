import uuid
from datetime import date, datetime, timezone

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class VideoStats(Base):
    """a snapshot of public stats taken every time we sync. rows just keep accumulating
    so you can see how views/likes grew over time."""

    __tablename__ = "video_stats"

    __table_args__ = (sa.Index("ix_video_stats_video_fetched", "video_id", "fetched_at"),)

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    video_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, sa.ForeignKey("videos.id", ondelete="CASCADE"))
    view_count: Mapped[int] = mapped_column(sa.BigInteger)
    like_count: Mapped[int] = mapped_column(sa.BigInteger)
    comment_count: Mapped[int] = mapped_column(sa.BigInteger)
    fetched_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)


class VideoAnalytics(Base):
    """the good stuff — one row per video per day from the analytics api.
    ctr, how long people watched, where they came from, etc."""

    __tablename__ = "video_analytics"

    __table_args__ = (
        sa.UniqueConstraint("video_id", "date", name="uq_video_analytics_video_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    video_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, sa.ForeignKey("videos.id", ondelete="CASCADE"))
    date: Mapped[date] = mapped_column(sa.Date)
    views: Mapped[int | None] = mapped_column(sa.Integer)
    estimated_minutes_watched: Mapped[float | None] = mapped_column(sa.Float)
    average_view_duration_seconds: Mapped[float | None] = mapped_column(sa.Float)
    average_view_percentage: Mapped[float | None] = mapped_column(sa.Float)
    click_through_rate: Mapped[float | None] = mapped_column(sa.Float)
    impressions: Mapped[int | None] = mapped_column(sa.Integer)
    likes: Mapped[int | None] = mapped_column(sa.Integer)
    comments: Mapped[int | None] = mapped_column(sa.Integer)
    shares: Mapped[int | None] = mapped_column(sa.Integer)
    subscribers_gained: Mapped[int | None] = mapped_column(sa.Integer)
    subscribers_lost: Mapped[int | None] = mapped_column(sa.Integer)
    traffic_source: Mapped[dict | None] = mapped_column(JSONB)
    fetched_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)
