import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Channel(Base):
    __tablename__ = "channels"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, sa.ForeignKey("users.id", ondelete="CASCADE"))
    youtube_channel_id: Mapped[str] = mapped_column(sa.String(255), unique=True)
    title: Mapped[str] = mapped_column(sa.String(255))
    description: Mapped[str | None] = mapped_column(sa.Text)
    custom_url: Mapped[str | None] = mapped_column(sa.String(255))
    thumbnail_url: Mapped[str | None] = mapped_column(sa.Text)
    subscriber_count: Mapped[int | None] = mapped_column(sa.BigInteger)
    video_count: Mapped[int | None] = mapped_column(sa.Integer)
    view_count: Mapped[int | None] = mapped_column(sa.BigInteger)
    published_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    last_synced_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)
