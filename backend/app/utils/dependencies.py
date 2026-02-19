import uuid

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.users import User


async def get_current_user(
    request: Request, db: AsyncSession = Depends(get_db)
) -> User:
    """reads the session cookie and returns the logged-in user.
    drop this as a dependency on any route that requires authentication."""
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="not logged in")

    user = await db.get(User, uuid.UUID(user_id))
    if not user:
        raise HTTPException(status_code=401, detail="user not found")

    return user
