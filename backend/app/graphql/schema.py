import uuid

import strawberry
from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from strawberry.types import Info

from app.models.channels import Channel
from app.models.stats import VideoStats
from app.models.users import User
from app.models.videos import Video

from .types import ChannelType, UserType, VideosPage, VideoStatsType, VideoType

SORT_COLUMNS = {
    "views": VideoStats.view_count,
    "likes": VideoStats.like_count,
    "comments": VideoStats.comment_count,
    "published_at": Video.published_at,
    "duration": Video.duration_seconds,
    "title": Video.title,
}


def _require_user(info: Info) -> uuid.UUID:
    """reads the session cookie and returns the user id, raises if not logged in."""
    user_id = info.context["request"].session.get("user_id")
    if not user_id:
        raise PermissionError("not logged in")
    return uuid.UUID(user_id)


def _map_video(v: Video, s: VideoStats | None, all_stats: list[VideoStats]) -> VideoType:
    """converts db rows into the strawberry VideoType."""
    return VideoType(
        id=strawberry.ID(str(v.id)),
        youtube_video_id=v.youtube_video_id,
        title=v.title,
        description=v.description,
        published_at=v.published_at,
        duration_seconds=v.duration_seconds,
        is_short=v.is_short,
        thumbnail_url=v.thumbnail_url,
        tags=v.tags,
        category_id=v.category_id,
        default_language=v.default_language,
        latest_stats=(
            VideoStatsType(
                view_count=s.view_count,
                like_count=s.like_count,
                comment_count=s.comment_count,
                fetched_at=s.fetched_at,
            )
            if s
            else None
        ),
        stats_history=[
            VideoStatsType(
                view_count=stat.view_count,
                like_count=stat.like_count,
                comment_count=stat.comment_count,
                fetched_at=stat.fetched_at,
            )
            for stat in all_stats
        ],
    )


@strawberry.type
class Query:
    @strawberry.field
    async def me(self, info: Info) -> UserType:
        """returns the currently logged-in user's profile."""
        user_id = _require_user(info)
        db: AsyncSession = info.context["db"]

        user = await db.get(User, user_id)
        if not user:
            raise PermissionError("user not found")

        return UserType(
            id=strawberry.ID(str(user.id)),
            email=user.email,
            name=user.name,
            picture_url=user.picture_url,
        )

    @strawberry.field
    async def channels(self, info: Info) -> list[ChannelType]:
        """returns all youtube channels connected to the logged-in user."""
        user_id = _require_user(info)
        db: AsyncSession = info.context["db"]

        result = await db.execute(
            select(Channel).where(Channel.user_id == user_id)
        )
        channels = result.scalars().all()

        return [
            ChannelType(
                id=strawberry.ID(str(c.id)),
                youtube_channel_id=c.youtube_channel_id,
                title=c.title,
                description=c.description,
                custom_url=c.custom_url,
                thumbnail_url=c.thumbnail_url,
                subscriber_count=c.subscriber_count,
                video_count=c.video_count,
                view_count=c.view_count,
                published_at=c.published_at,
                last_synced_at=c.last_synced_at,
            )
            for c in channels
        ]

    @strawberry.field
    async def channel(self, info: Info, id: strawberry.ID) -> ChannelType | None:
        """returns a single channel by id — only if it belongs to the logged-in user."""
        user_id = _require_user(info)
        db: AsyncSession = info.context["db"]

        c = await db.get(Channel, uuid.UUID(str(id)))
        if not c or c.user_id != user_id:
            return None

        return ChannelType(
            id=strawberry.ID(str(c.id)),
            youtube_channel_id=c.youtube_channel_id,
            title=c.title,
            description=c.description,
            custom_url=c.custom_url,
            thumbnail_url=c.thumbnail_url,
            subscriber_count=c.subscriber_count,
            video_count=c.video_count,
            view_count=c.view_count,
            published_at=c.published_at,
            last_synced_at=c.last_synced_at,
        )

    @strawberry.field
    async def videos(
        self,
        info: Info,
        channel_id: strawberry.ID,
        sort_by: str = "published_at",
        order: str = "desc",
        page: int = 1,
        per_page: int = 50,
    ) -> VideosPage:
        """returns a paginated list of videos for a channel with their latest stats."""
        user_id = _require_user(info)
        db: AsyncSession = info.context["db"]

        # ownership check
        channel_uuid = uuid.UUID(str(channel_id))
        channel = await db.get(Channel, channel_uuid)
        if not channel or channel.user_id != user_id:
            raise ValueError("channel not found")

        if sort_by not in SORT_COLUMNS:
            sort_by = "published_at"
        if order not in ("asc", "desc"):
            order = "desc"

        # subquery to get the latest stats snapshot per video
        latest_stats_sq = (
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
            .join(latest_stats_sq, latest_stats_sq.c.video_id == Video.id)
            .join(
                VideoStats,
                (VideoStats.video_id == Video.id)
                & (VideoStats.fetched_at == latest_stats_sq.c.latest_fetch),
            )
            .where(Video.channel_id == channel_uuid)
            .order_by(direction(sort_col))
            .offset((page - 1) * per_page)
            .limit(per_page)
        )

        rows = (await db.execute(query)).all()

        count_query = select(func.count(Video.id)).where(Video.channel_id == channel_uuid)
        total = (await db.execute(count_query)).scalar_one()

        return VideosPage(
            total=total,
            page=page,
            per_page=per_page,
            items=[_map_video(v, s, []) for v, s in rows],
        )

    @strawberry.field
    async def video(self, info: Info, id: strawberry.ID) -> VideoType | None:
        """returns a single video with its full stats history."""
        user_id = _require_user(info)
        db: AsyncSession = info.context["db"]

        video_uuid = uuid.UUID(str(id))
        v = await db.get(Video, video_uuid)
        if not v:
            return None

        # verify ownership through the channel
        channel = await db.get(Channel, v.channel_id)
        if not channel or channel.user_id != user_id:
            return None

        # get all stats snapshots ordered oldest → newest
        stats_result = await db.execute(
            select(VideoStats)
            .where(VideoStats.video_id == video_uuid)
            .order_by(VideoStats.fetched_at)
        )
        all_stats = stats_result.scalars().all()

        latest = all_stats[-1] if all_stats else None
        return _map_video(v, latest, all_stats)


schema = strawberry.Schema(query=Query)
