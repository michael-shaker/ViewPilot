from datetime import datetime

import strawberry


@strawberry.type
class UserType:
    id: strawberry.ID
    email: str
    name: str
    picture_url: str | None


@strawberry.type
class ChannelType:
    id: strawberry.ID
    youtube_channel_id: str
    title: str
    description: str | None
    custom_url: str | None
    thumbnail_url: str | None
    subscriber_count: int | None
    video_count: int | None
    view_count: int | None
    published_at: datetime | None
    last_synced_at: datetime | None


@strawberry.type
class VideoStatsType:
    view_count: int
    like_count: int
    comment_count: int
    fetched_at: datetime


@strawberry.type
class VideoType:
    id: strawberry.ID
    youtube_video_id: str
    title: str
    description: str | None
    published_at: datetime
    duration_seconds: int | None
    is_short: bool
    thumbnail_url: str | None
    tags: list[str] | None
    category_id: str | None
    default_language: str | None
    latest_stats: VideoStatsType | None
    stats_history: list[VideoStatsType]


@strawberry.type
class VideosPage:
    total: int
    page: int
    per_page: int
    items: list[VideoType]
