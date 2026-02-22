from datetime import datetime
from typing import Optional

import strawberry


@strawberry.type
class UserType:
    id: strawberry.ID
    email: str
    name: str
    picture_url: Optional[str]


@strawberry.type
class ChannelType:
    id: strawberry.ID
    youtube_channel_id: str
    title: str
    description: Optional[str]
    custom_url: Optional[str]
    thumbnail_url: Optional[str]
    subscriber_count: Optional[int]
    video_count: Optional[int]
    view_count: Optional[int]
    published_at: Optional[datetime]
    last_synced_at: Optional[datetime]


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
    description: Optional[str]
    published_at: datetime
    duration_seconds: Optional[int]
    is_short: bool
    thumbnail_url: Optional[str]
    tags: Optional[list[str]]
    category_id: Optional[str]
    default_language: Optional[str]
    latest_stats: Optional[VideoStatsType]
    stats_history: list[VideoStatsType]


@strawberry.type
class VideosPage:
    total: int
    page: int
    per_page: int
    items: list[VideoType]
