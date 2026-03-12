import uuid
from datetime import UTC, date, datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


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
    # revenue data — requires yt-analytics-monetary.readonly scope
    estimated_revenue: Mapped[float | None] = mapped_column(sa.Float)
    estimated_ad_revenue: Mapped[float | None] = mapped_column(sa.Float)
    rpm: Mapped[float | None] = mapped_column(sa.Float)
    cpm: Mapped[float | None] = mapped_column(sa.Float)
    fetched_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)


class ChannelDailyStats(Base):
    """real daily channel totals fetched from the analytics api with dimensions=day.
    one row per channel per calendar day — the source of truth for the charts page."""

    __tablename__ = "channel_daily_stats"

    __table_args__ = (
        sa.UniqueConstraint("channel_id", "date", name="uq_channel_daily_stats_channel_date"),
        sa.Index("ix_channel_daily_stats_channel_date", "channel_id", "date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    channel_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, sa.ForeignKey("channels.id", ondelete="CASCADE"))
    date: Mapped[date] = mapped_column(sa.Date)
    # core metrics — always available
    views: Mapped[int | None] = mapped_column(sa.Integer)
    estimated_minutes_watched: Mapped[float | None] = mapped_column(sa.Float)
    average_view_duration_seconds: Mapped[float | None] = mapped_column(sa.Float)
    likes: Mapped[int | None] = mapped_column(sa.Integer)
    comments: Mapped[int | None] = mapped_column(sa.Integer)
    subscribers_gained: Mapped[int | None] = mapped_column(sa.Integer)
    subscribers_lost: Mapped[int | None] = mapped_column(sa.Integer)
    # reach metrics — available from ~2018 onwards, stored as 0–1 fraction
    impressions: Mapped[int | None] = mapped_column(sa.Integer)
    click_through_rate: Mapped[float | None] = mapped_column(sa.Float)
    # revenue — requires yt-analytics-monetary.readonly scope
    estimated_revenue: Mapped[float | None] = mapped_column(sa.Float)
    fetched_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)
