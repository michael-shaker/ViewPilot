from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.channels import Channel
from app.models.users import User
from app.services.sync import sync_channel
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/channels", tags=["channels"])


@router.get("")
async def list_channels(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """return all youtube channels connected to the logged-in user."""
    result = await db.execute(
        select(Channel).where(Channel.user_id == current_user.id)
    )
    channels = result.scalars().all()
    return [
        {
            "id": str(c.id),
            "youtube_channel_id": c.youtube_channel_id,
            "title": c.title,
            "thumbnail_url": c.thumbnail_url,
            "subscriber_count": c.subscriber_count,
            "video_count": c.video_count,
            "view_count": c.view_count,
            "last_synced_at": c.last_synced_at,
        }
        for c in channels
    ]


@router.post("/sync")
async def trigger_sync(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """kick off a full sync — fetches channel info and all videos from youtube
    and saves everything to the database."""
    try:
        channel = await sync_channel(db, current_user)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {
        "ok": True,
        "channel_id": str(channel.id),
        "title": channel.title,
        "video_count": channel.video_count,
    }
