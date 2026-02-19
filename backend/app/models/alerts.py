import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Alert(Base):
    """a notification the app fires off — like when a video is underperforming after 48 hours."""

    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    channel_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("channels.id", ondelete="CASCADE")
    )
    video_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid, sa.ForeignKey("videos.id", ondelete="SET NULL"), nullable=True
    )
    alert_type: Mapped[str] = mapped_column(sa.String(50))
    message: Mapped[str] = mapped_column(sa.Text)
    is_read: Mapped[bool] = mapped_column(sa.Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)
