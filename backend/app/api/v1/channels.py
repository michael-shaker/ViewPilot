from fastapi import APIRouter, Depends, HTTPException, Request
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
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """kick off a full sync — fetches channel info and all videos from youtube
    and saves everything to the database."""
    try:
        channel = await sync_channel(db, current_user)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # bust all caches for this channel so fresh data shows immediately after sync
    redis = request.app.state.redis
    channel_id = str(channel.id)
    # delete autopsy cache
    for pct in [5, 10, 20, 25]:
        for ws in [10, 50, 100, 150, 200]:
            await redis.delete(f"autopsy:{channel_id}:{ws}:{pct}")
    # delete video list cache pages (covers common page/sort combos)
    async for key in redis.scan_iter(f"vlist:{channel_id}:*"):
        await redis.delete(key)
    # delete charts cache (all granularities)
    for granularity in ["daily", "weekly", "monthly"]:
        await redis.delete(f"charts:{channel_id}:{granularity}")

    return {
        "ok": True,
        "channel_id": channel_id,
        "title": channel.title,
        "video_count": channel.video_count,
    }
