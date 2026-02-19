import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.users import User
from app.utils.security import encrypt_token


async def get_or_create_user(
    db: AsyncSession,
    google_id: str,
    email: str,
    name: str,
    picture_url: str | None,
    access_token: str,
    refresh_token: str | None,
    token_expires_at: datetime | None,
) -> User:
    """look up the user by google id. if they've logged in before, update their tokens.
    if they're new, create their account."""
    result = await db.execute(select(User).where(User.google_id == google_id))
    user = result.scalar_one_or_none()

    encrypted_access = encrypt_token(access_token, settings.secret_key)
    encrypted_refresh = (
        encrypt_token(refresh_token, settings.secret_key) if refresh_token else None
    )

    if user:
        user.email = email
        user.name = name
        user.picture_url = picture_url
        user.access_token = encrypted_access
        if encrypted_refresh:
            user.refresh_token = encrypted_refresh
        user.token_expires_at = token_expires_at
    else:
        user = User(
            id=uuid.uuid4(),
            google_id=google_id,
            email=email,
            name=name,
            picture_url=picture_url,
            access_token=encrypted_access,
            refresh_token=encrypted_refresh,
            token_expires_at=token_expires_at,
        )
        db.add(user)

    await db.commit()
    await db.refresh(user)
    return user
