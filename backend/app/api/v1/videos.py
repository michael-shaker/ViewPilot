from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.channels import Channel
from app.models.videos import Video
from app.models.stats import VideoStats
from app.models.users import User
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/videos", tags=["videos"])

SORT_COLUMNS = {
    "views": VideoStats.view_count,
    "likes": VideoStats.like_count,
    "comments": VideoStats.comment_count,
    "published_at": Video.published_at,
    "duration": Video.duration_seconds,
    "title": Video.title,
}


@router.get("")
async def list_videos(
    channel_id: UUID,
    sort_by: str = Query(default="published_at", enum=list(SORT_COLUMNS)),
    order: str = Query(default="desc", enum=["asc", "desc"]),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """return a paginated list of videos for a channel, with sorting."""
    # make sure this channel belongs to the logged-in user
    channel = await db.get(Channel, channel_id)
    if not channel or channel.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="channel not found")

    # get the latest stats snapshot per video using a subquery
    latest_stats = (
        select(
            VideoStats.video_id,
            func.max(VideoStats.fetched_at).label("latest_fetch"),
        )
        .group_by(VideoStats.video_id)
        .subquery()
    )

    sort_col = SORT_COLUMNS[sort_by]
    direction = desc if order == "desc" else asc

    query = (
        select(Video, VideoStats)
        .join(latest_stats, latest_stats.c.video_id == Video.id)
        .join(
            VideoStats,
            (VideoStats.video_id == Video.id)
            & (VideoStats.fetched_at == latest_stats.c.latest_fetch),
        )
        .where(Video.channel_id == channel_id)
        .order_by(direction(sort_col))
        .offset((page - 1) * per_page)
        .limit(per_page)
    )

    result = await db.execute(query)
    rows = result.all()

    # get total count for pagination info
    count_query = select(func.count(Video.id)).where(Video.channel_id == channel_id)
    total = (await db.execute(count_query)).scalar_one()

    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "videos": [
            {
                "id": str(v.id),
                "youtube_video_id": v.youtube_video_id,
                "title": v.title,
                "published_at": v.published_at,
                "duration_seconds": v.duration_seconds,
                "is_short": v.is_short,
                "thumbnail_url": v.thumbnail_url,
                "tags": v.tags,
                "category_id": v.category_id,
                "view_count": s.view_count,
                "like_count": s.like_count,
                "comment_count": s.comment_count,
                "stats_fetched_at": s.fetched_at,
            }
            for v, s in rows
        ],
    }


@router.get("/{video_id}")
async def get_video(
    video_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """return a single video with its full stats history."""
    video = await db.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="video not found")

    # verify ownership via channel
    channel = await db.get(Channel, video.channel_id)
    if not channel or channel.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="video not found")

    # fetch all stats snapshots for this video
    stats_result = await db.execute(
        select(VideoStats)
        .where(VideoStats.video_id == video_id)
        .order_by(VideoStats.fetched_at)
    )
    stats_history = stats_result.scalars().all()

    return {
        "id": str(video.id),
        "youtube_video_id": video.youtube_video_id,
        "title": video.title,
        "description": video.description,
        "published_at": video.published_at,
        "duration_seconds": video.duration_seconds,
        "is_short": video.is_short,
        "thumbnail_url": video.thumbnail_url,
        "tags": video.tags,
        "category_id": video.category_id,
        "default_language": video.default_language,
        "stats_history": [
            {
                "view_count": s.view_count,
                "like_count": s.like_count,
                "comment_count": s.comment_count,
                "fetched_at": s.fetched_at,
            }
            for s in stats_history
        ],
    }
