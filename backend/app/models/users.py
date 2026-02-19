import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    google_id: Mapped[str] = mapped_column(sa.String(255), unique=True)
    email: Mapped[str] = mapped_column(sa.String(255))
    name: Mapped[str] = mapped_column(sa.String(255))
    picture_url: Mapped[str | None] = mapped_column(sa.Text)
    access_token: Mapped[str | None] = mapped_column(sa.Text)
    refresh_token: Mapped[str | None] = mapped_column(sa.Text)
    token_expires_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
