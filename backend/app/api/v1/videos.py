import asyncio
import json
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import asc, delete, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.channels import Channel
from app.models.stats import VideoAnalytics, VideoStats
from app.models.users import User
from app.models.videos import Video, VideoComment
from app.services import youtube as yt
from app.utils.dependencies import get_current_user
from app.utils.security import decrypt_token

router = APIRouter(prefix="/videos", tags=["videos"])

SORT_COLUMNS = {
    "views": VideoStats.view_count,
    "likes": VideoStats.like_count,
    "comments": VideoStats.comment_count,
    "published_at": Video.published_at,
    "duration": Video.duration_seconds,
    "title": Video.title,
    "revenue": VideoAnalytics.estimated_revenue,
    "rpm": VideoAnalytics.rpm,
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

    # get the most recent analytics row per video (outer join — not all videos have data yet)
    latest_analytics = (
        select(
            VideoAnalytics.video_id,
            func.max(VideoAnalytics.date).label("latest_date"),
        )
        .group_by(VideoAnalytics.video_id)
        .subquery()
    )

    sort_col = SORT_COLUMNS[sort_by]
    direction = desc if order == "desc" else asc

    query = (
        select(Video, VideoStats, VideoAnalytics)
        .join(latest_stats, latest_stats.c.video_id == Video.id)
        .join(
            VideoStats,
            (VideoStats.video_id == Video.id)
            & (VideoStats.fetched_at == latest_stats.c.latest_fetch),
        )
        .outerjoin(latest_analytics, latest_analytics.c.video_id == Video.id)
        .outerjoin(
            VideoAnalytics,
            (VideoAnalytics.video_id == Video.id)
            & (VideoAnalytics.date == latest_analytics.c.latest_date),
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
                "views_per_day": round(
                    s.view_count / max((date.today() - v.published_at.date()).days, 1), 1
                ),
                "click_through_rate": a.click_through_rate if a else None,
                "impressions": a.impressions if a else None,
                "average_view_duration_seconds": a.average_view_duration_seconds if a else None,
                "average_view_percentage": (
                    a.average_view_percentage
                    if (a and a.average_view_percentage is not None)
                    else round(a.average_view_duration_seconds / v.duration_seconds * 100, 1)
                    if (a and a.average_view_duration_seconds and v.duration_seconds)
                    else None
                ),
                "estimated_revenue": a.estimated_revenue if a else None,
                "rpm": a.rpm if a else None,
            }
            for v, s, a in rows
        ],
    }


@router.get("/dislikes")
async def get_video_dislikes(
    request: Request,
    ids: str = Query(..., description="comma-separated youtube video ids"),
    current_user: User = Depends(get_current_user),
):
    """return dislike counts for a list of youtube video ids.
    results are cached in redis for 24 hours to avoid hammering the ryd api on every page load."""
    youtube_ids = [i.strip() for i in ids.split(",") if i.strip()][:100]
    redis = request.app.state.redis

    results: dict[str, int | None] = {}
    missing: list[str] = []

    # check redis for each id first
    for yt_id in youtube_ids:
        cached = await redis.get(f"dislikes:{yt_id}")
        if cached is not None:
            results[yt_id] = int(cached)
        else:
            missing.append(yt_id)

    # fetch any uncached ids from the ryd api in parallel
    if missing:
        async with httpx.AsyncClient(timeout=8) as client:
            responses = await asyncio.gather(
                *[client.get(f"https://returnyoutubedislikeapi.com/votes?videoId={vid}") for vid in missing],
                return_exceptions=True,
            )
            for yt_id, resp in zip(missing, responses):
                if isinstance(resp, Exception):
                    results[yt_id] = None
                    continue
                try:
                    count = int(resp.json().get("dislikes", 0))
                    results[yt_id] = count
                    await redis.set(f"dislikes:{yt_id}", str(count), ex=86400)  # cache 24h
                except Exception:
                    results[yt_id] = None

    return results


@router.get("/{video_id}")
async def get_video(
    video_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """return a single video with its full stats + analytics."""
    video = await db.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="video not found")

    # verify ownership via channel
    channel = await db.get(Channel, video.channel_id)
    if not channel or channel.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="video not found")

    # all stats snapshots, newest first
    stats_result = await db.execute(
        select(VideoStats)
        .where(VideoStats.video_id == video_id)
        .order_by(VideoStats.fetched_at.desc())
    )
    stats_history = stats_result.scalars().all()

    # latest analytics row
    analytics_result = await db.execute(
        select(VideoAnalytics)
        .where(VideoAnalytics.video_id == video_id)
        .order_by(VideoAnalytics.date.desc())
        .limit(1)
    )
    analytics = analytics_result.scalar_one_or_none()

    latest = stats_history[0] if stats_history else None
    days_live = max((date.today() - video.published_at.date()).days, 1)

    return {
        "id": str(video.id),
        "youtube_video_id": video.youtube_video_id,
        "title": video.title,
        "description": video.description,
        "published_at": video.published_at,
        "duration_seconds": video.duration_seconds,
        "is_short": video.is_short,
        "thumbnail_url": video.thumbnail_url,
        "tags": video.tags or [],
        "category_id": video.category_id,
        "default_language": video.default_language,
        # latest counts pulled out for easy access
        "view_count": latest.view_count if latest else 0,
        "like_count": latest.like_count if latest else 0,
        "comment_count": latest.comment_count if latest else 0,
        "views_per_day": round(latest.view_count / days_live, 1) if latest else None,
        "engagement_rate": round(latest.like_count / latest.view_count * 100, 2) if latest and latest.view_count else None,
        # analytics api data
        "click_through_rate": analytics.click_through_rate if analytics else None,
        "impressions": analytics.impressions if analytics else None,
        "average_view_duration_seconds": analytics.average_view_duration_seconds if analytics else None,
        "average_view_percentage": (
            analytics.average_view_percentage
            if (analytics and analytics.average_view_percentage is not None)
            else round(analytics.average_view_duration_seconds / video.duration_seconds * 100, 1)
            if (analytics and analytics.average_view_duration_seconds and video.duration_seconds)
            else None
        ),
        "estimated_minutes_watched": analytics.estimated_minutes_watched if analytics else None,
        "estimated_revenue": analytics.estimated_revenue if analytics else None,
        "estimated_ad_revenue": analytics.estimated_ad_revenue if analytics else None,
        "rpm": analytics.rpm if analytics else None,
        "cpm": analytics.cpm if analytics else None,
        # full history for the table
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


@router.get("/{video_id}/history")
async def get_video_history(
    request: Request,
    video_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """fetch real daily view/like/comment counts from the youtube analytics api
    for a single video, from its publish date up to today.
    cached in redis for 24 hours — analytics data only updates once a day anyway."""
    video = await db.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="video not found")

    channel = await db.get(Channel, video.channel_id)
    if not channel or channel.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="video not found")

    # return cached result if we have one — avoids hitting youtube analytics api every page load
    redis = request.app.state.redis
    cache_key = f"history:{video_id}"
    cached = await redis.get(cache_key)
    if cached:
        return {"daily": json.loads(cached)}

    access_token = decrypt_token(current_user.access_token, settings.secret_key)
    refresh_token = (
        decrypt_token(current_user.refresh_token, settings.secret_key)
        if current_user.refresh_token
        else None
    )

    start_date = video.published_at.strftime("%Y-%m-%d")

    try:
        daily = await yt.get_video_daily_history(
            access_token, refresh_token, video.youtube_video_id, start_date
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"analytics api error: {exc}")

    # cache for 24 hours — the analytics api only updates once a day so this is always fresh enough
    await redis.set(cache_key, json.dumps(daily), ex=86400)

    return {"daily": daily}


@router.get("/{video_id}/comments")
async def get_video_comments(
    video_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """return the top 10 comments + all replies for a video.
    results are cached in the db for 6 hours to avoid burning api quota."""
    video = await db.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="video not found")

    channel = await db.get(Channel, video.channel_id)
    if not channel or channel.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="video not found")

    # check for cached comments less than 6 hours old
    fresh_cutoff = datetime.now(UTC) - timedelta(hours=6)
    cached_result = await db.execute(
        select(VideoComment)
        .where(VideoComment.video_id == video_id)
        .where(VideoComment.fetched_at > fresh_cutoff)
        .order_by(VideoComment.is_reply, VideoComment.like_count.desc())
    )
    cached = cached_result.scalars().all()

    if cached:
        return _format_comments(cached)

    # cache is stale or empty — fetch fresh from youtube api
    access_token = decrypt_token(current_user.access_token, settings.secret_key)
    refresh_token = (
        decrypt_token(current_user.refresh_token, settings.secret_key)
        if current_user.refresh_token
        else None
    )

    raw = await yt.get_video_comments(access_token, refresh_token, video.youtube_video_id)
    print(f"[comments] fetched {len(raw)} comments for {video.youtube_video_id}")

    # wipe old cached rows and store new ones
    await db.execute(delete(VideoComment).where(VideoComment.video_id == video_id))

    now = datetime.now(UTC)
    for c in raw:
        db.add(VideoComment(
            video_id=video_id,
            youtube_comment_id=c["youtube_comment_id"],
            parent_youtube_id=c["parent_youtube_id"],
            author_name=c["author_name"],
            author_image_url=c["author_image_url"],
            author_channel_url=c["author_channel_url"],
            author_channel_id=c["author_channel_id"],
            text=c["text"],
            like_count=c["like_count"],
            reply_count=c["reply_count"],
            is_reply=c["is_reply"],
            published_at=_parse_yt_dt(c["published_at"]),
            updated_at_youtube=_parse_yt_dt(c["updated_at_youtube"]),
            fetched_at=now,
        ))
    await db.commit()

    # re-query from db to get ids etc
    result = await db.execute(
        select(VideoComment)
        .where(VideoComment.video_id == video_id)
        .order_by(VideoComment.is_reply, VideoComment.like_count.desc())
    )
    return _format_comments(result.scalars().all())


def _parse_yt_dt(s: str | None) -> datetime | None:
    """parse youtube's iso 8601 timestamp strings into aware datetimes."""
    if not s:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _format_comments(rows: list[VideoComment]) -> dict:
    """organize flat db rows into top-level comments each with their replies nested."""
    top_level = {}
    replies: dict[str, list] = {}

    for c in rows:
        obj = {
            "id": str(c.id),
            "youtube_comment_id": c.youtube_comment_id,
            "parent_youtube_id": c.parent_youtube_id,
            "author_name": c.author_name,
            "author_image_url": c.author_image_url,
            "author_channel_url": c.author_channel_url,
            "text": c.text,
            "like_count": c.like_count,
            "reply_count": c.reply_count,
            "is_reply": c.is_reply,
            "published_at": c.published_at,
        }
        if not c.is_reply:
            top_level[c.youtube_comment_id] = {**obj, "replies": []}
        else:
            parent = c.parent_youtube_id or ""
            replies.setdefault(parent, []).append(obj)

    # attach replies to their parent
    for parent_id, reply_list in replies.items():
        if parent_id in top_level:
            top_level[parent_id]["replies"] = sorted(reply_list, key=lambda r: r["like_count"], reverse=True)

    return {"comments": list(top_level.values())}
