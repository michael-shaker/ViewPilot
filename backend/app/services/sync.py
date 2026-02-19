import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.channels import Channel
from app.models.users import User
from app.models.videos import Video
from app.models.stats import VideoStats
from app.services import youtube as yt
from app.utils.security import decrypt_token
from app.utils.youtube_parser import parse_duration, best_thumbnail
from app.config import settings


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def sync_channel(db: AsyncSession, user: User) -> Channel:
    """full sync for a user's youtube channel.
    fetches channel info, all videos, and saves a stats snapshot for each."""

    # decrypt the stored oauth tokens so we can call the youtube api
    access_token = decrypt_token(user.access_token, settings.secret_key)
    refresh_token = (
        decrypt_token(user.refresh_token, settings.secret_key)
        if user.refresh_token
        else None
    )

    # ── step 1: fetch and upsert channel ─────────────────────────────────────
    channel_data = await yt.get_channel_info(access_token, refresh_token)
    snippet = channel_data["snippet"]
    stats = channel_data["statistics"]
    uploads_playlist_id = (
        channel_data["contentDetails"]["relatedPlaylists"]["uploads"]
    )

    result = await db.execute(
        select(Channel).where(Channel.youtube_channel_id == channel_data["id"])
    )
    channel = result.scalar_one_or_none()

    if channel:
        channel.title = snippet["title"]
        channel.description = snippet.get("description")
        channel.custom_url = snippet.get("customUrl")
        channel.thumbnail_url = best_thumbnail(snippet.get("thumbnails", {}))
        channel.subscriber_count = int(stats.get("subscriberCount", 0))
        channel.video_count = int(stats.get("videoCount", 0))
        channel.view_count = int(stats.get("viewCount", 0))
        channel.last_synced_at = _utcnow()
    else:
        channel = Channel(
            id=uuid.uuid4(),
            user_id=user.id,
            youtube_channel_id=channel_data["id"],
            title=snippet["title"],
            description=snippet.get("description"),
            custom_url=snippet.get("customUrl"),
            thumbnail_url=best_thumbnail(snippet.get("thumbnails", {})),
            subscriber_count=int(stats.get("subscriberCount", 0)),
            video_count=int(stats.get("videoCount", 0)),
            view_count=int(stats.get("viewCount", 0)),
            published_at=datetime.fromisoformat(
                snippet["publishedAt"].replace("Z", "+00:00")
            ),
            last_synced_at=_utcnow(),
        )
        db.add(channel)

    await db.flush()  # get channel.id before we need it for videos

    # ── step 2: fetch all video ids ───────────────────────────────────────────
    video_ids = await yt.get_all_video_ids(
        access_token, refresh_token, uploads_playlist_id
    )

    # ── step 3: batch fetch video metadata (50 at a time) ────────────────────
    for i in range(0, len(video_ids), 50):
        batch_ids = video_ids[i : i + 50]
        items = await yt.get_videos_batch(access_token, refresh_token, batch_ids)

        for item in items:
            s = item["snippet"]
            cd = item["contentDetails"]
            st = item["statistics"]

            duration_seconds = parse_duration(cd.get("duration", ""))
            published_at = datetime.fromisoformat(
                s["publishedAt"].replace("Z", "+00:00")
            )

            # check if video already exists
            existing = await db.execute(
                select(Video).where(Video.youtube_video_id == item["id"])
            )
            video = existing.scalar_one_or_none()

            if video:
                video.title = s["title"]
                video.description = s.get("description")
                video.tags = s.get("tags", [])
                video.category_id = s.get("categoryId")
                video.duration_seconds = duration_seconds
                video.thumbnail_url = best_thumbnail(s.get("thumbnails", {}))
                video.default_language = s.get("defaultLanguage")
                video.is_short = duration_seconds < 60
            else:
                video = Video(
                    id=uuid.uuid4(),
                    channel_id=channel.id,
                    youtube_video_id=item["id"],
                    title=s["title"],
                    description=s.get("description"),
                    tags=s.get("tags", []),
                    category_id=s.get("categoryId"),
                    duration_seconds=duration_seconds,
                    published_at=published_at,
                    thumbnail_url=best_thumbnail(s.get("thumbnails", {})),
                    default_language=s.get("defaultLanguage"),
                    is_short=duration_seconds < 60,
                )
                db.add(video)

            await db.flush()

            # save a stats snapshot every sync
            snapshot = VideoStats(
                id=uuid.uuid4(),
                video_id=video.id,
                view_count=int(st.get("viewCount", 0)),
                like_count=int(st.get("likeCount", 0)),
                comment_count=int(st.get("commentCount", 0)),
                fetched_at=_utcnow(),
            )
            db.add(snapshot)

    await db.commit()
    await db.refresh(channel)
    return channel
