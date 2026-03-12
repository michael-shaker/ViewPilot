import uuid
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.channels import Channel
from app.models.stats import ChannelDailyStats, VideoAnalytics, VideoStats
from app.models.users import User
from app.models.videos import Video
from app.services import youtube as yt
from app.utils.security import decrypt_token
from app.utils.youtube_parser import best_thumbnail, parse_duration


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _safe_int(val) -> int | None:
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _safe_float(val) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


async def _sync_analytics(
    db: AsyncSession,
    access_token: str,
    refresh_token: str | None,
    channel: Channel,
) -> None:
    """pulls all analytics data for this channel's videos and saves it.
    split into two independent steps — if one fails the other still runs."""

    today = datetime.now(UTC).date()

    # shared lookup: youtube video id → our internal db video id
    result = await db.execute(
        select(Video.youtube_video_id, Video.id).where(Video.channel_id == channel.id)
    )
    yt_to_db = {row[0]: row[1] for row in result.all()}

    # ── step a: analytics api (views, avg watch time, avg watch %) ────────────
    # one api call returns lifetime aggregates for every video at once.
    # keep analytics_data in outer scope so step b can use views for rpm calculation
    analytics_data: dict = {}
    try:
        analytics_data = await yt.get_channel_analytics(access_token, refresh_token)
        for yt_vid_id, data in analytics_data.items():
            db_vid_id = yt_to_db.get(yt_vid_id)
            if not db_vid_id:
                continue
            stmt = (
                pg_insert(VideoAnalytics)
                .values(
                    id=uuid.uuid4(),
                    video_id=db_vid_id,
                    date=today,
                    views=_safe_int(data.get("views")),
                    estimated_minutes_watched=_safe_float(data.get("estimatedMinutesWatched")),
                    average_view_duration_seconds=_safe_float(data.get("averageViewDuration")),
                    average_view_percentage=_safe_float(data.get("averageViewPercentage")),
                    likes=_safe_int(data.get("likes")),
                    comments=_safe_int(data.get("comments")),
                    shares=_safe_int(data.get("shares")),
                    subscribers_gained=_safe_int(data.get("subscribersGained")),
                    subscribers_lost=_safe_int(data.get("subscribersLost")),
                    fetched_at=_utcnow(),
                )
                .on_conflict_do_update(
                    constraint="uq_video_analytics_video_date",
                    set_={
                        "views": _safe_int(data.get("views")),
                        "estimated_minutes_watched": _safe_float(data.get("estimatedMinutesWatched")),
                        "average_view_duration_seconds": _safe_float(data.get("averageViewDuration")),
                        "average_view_percentage": _safe_float(data.get("averageViewPercentage")),
                        "likes": _safe_int(data.get("likes")),
                        "comments": _safe_int(data.get("comments")),
                        "shares": _safe_int(data.get("shares")),
                        "subscribers_gained": _safe_int(data.get("subscribersGained")),
                        "subscribers_lost": _safe_int(data.get("subscribersLost")),
                        "fetched_at": _utcnow(),
                    },
                )
            )
            await db.execute(stmt)
        print(f"analytics api: saved data for {len(analytics_data)} videos")
    except Exception as exc:
        print(f"analytics api step skipped: {exc}")

    # ── step b: revenue api (estimated revenue per video) ────────────────────
    # requires yt-analytics-monetary.readonly scope — gracefully skipped if user
    # hasn't re-authorized with the new scope yet.
    # rpm and cpm are not supported as per-video api metrics, so we calculate
    # rpm ourselves: (estimatedRevenue / views) * 1000
    try:
        revenue_data = await yt.get_channel_revenue(access_token, refresh_token)
        for yt_vid_id, data in revenue_data.items():
            db_vid_id = yt_to_db.get(yt_vid_id)
            if not db_vid_id:
                continue
            rev = _safe_float(data.get("estimatedRevenue"))
            ad_rev = _safe_float(data.get("estimatedAdRevenue"))
            # use views from step a's analytics data to calculate rpm (revenue per 1000 views)
            views = _safe_float(analytics_data.get(yt_vid_id, {}).get("views")) if analytics_data else None
            rpm = round(rev / views * 1000, 4) if rev is not None and views and views > 0 else None
            stmt = (
                pg_insert(VideoAnalytics)
                .values(
                    id=uuid.uuid4(),
                    video_id=db_vid_id,
                    date=today,
                    estimated_revenue=rev,
                    estimated_ad_revenue=ad_rev,
                    rpm=rpm,
                    fetched_at=_utcnow(),
                )
                .on_conflict_do_update(
                    constraint="uq_video_analytics_video_date",
                    set_={
                        "estimated_revenue": rev,
                        "estimated_ad_revenue": ad_rev,
                        "rpm": rpm,
                        "fetched_at": _utcnow(),
                    },
                )
            )
            await db.execute(stmt)
        print(f"revenue api: saved data for {len(revenue_data)} videos")
    except Exception as exc:
        print(f"revenue api step skipped: {exc}")

    # ── step c: reporting api (impressions + ctr from daily csv reports) ──────
    # impressions/ctr aren't available in the analytics api — they come from
    # a separate "reporting api" that generates daily csv files we download.
    # we sum up all available daily rows to get per-video totals, then
    # store them alongside the analytics data we just saved above.
    try:
        job_id = await yt.ensure_reach_job(access_token, refresh_token)
        reach_rows = await yt.download_reach_reports(access_token, refresh_token, job_id)

        if reach_rows:
            # aggregate all daily rows into per-video totals
            # weighted avg ctr = sum(impressions × ctr) / total impressions
            total_impressions: dict = defaultdict(int)
            weighted_ctr: dict = defaultdict(float)

            for row in reach_rows:
                vid = row["video_id"]
                total_impressions[vid] += row["impressions"]
                weighted_ctr[vid] += row["impressions"] * row["ctr"]

            # upsert impressions + ctr into the same row we created in step a
            # (or create a new row if step a didn't run for this video)
            for yt_vid_id, imp_total in total_impressions.items():
                db_vid_id = yt_to_db.get(yt_vid_id)
                if not db_vid_id:
                    continue
                avg_ctr = weighted_ctr[yt_vid_id] / imp_total if imp_total > 0 else None
                stmt = (
                    pg_insert(VideoAnalytics)
                    .values(
                        id=uuid.uuid4(),
                        video_id=db_vid_id,
                        date=today,
                        impressions=imp_total,
                        click_through_rate=avg_ctr,
                        fetched_at=_utcnow(),
                    )
                    .on_conflict_do_update(
                        constraint="uq_video_analytics_video_date",
                        set_={
                            "impressions": imp_total,
                            "click_through_rate": avg_ctr,
                            "fetched_at": _utcnow(),
                        },
                    )
                )
                await db.execute(stmt)
            print(f"reach reports: saved impressions/ctr for {len(total_impressions)} videos")
        else:
            print("reach reports: no csv data available yet (job may be newly created — try again tomorrow)")
    except Exception as exc:
        print(f"reach reports step skipped: {exc}")


async def _sync_channel_history(
    db: AsyncSession,
    access_token: str,
    refresh_token: str | None,
    channel: Channel,
) -> None:
    """fetch and store daily channel-level analytics going all the way back to channel launch.
    on the very first run this pulls the full history — could be years of data.
    on subsequent runs it only refreshes the last 60 days (youtube revises recent numbers)."""

    today = datetime.now(UTC).date()

    # check how many daily rows we already have for this channel
    existing_count = await db.scalar(
        select(func.count()).select_from(ChannelDailyStats).where(
            ChannelDailyStats.channel_id == channel.id
        )
    )

    if existing_count == 0:
        # first ever run — pull from channel launch date (youtube analytics starts ~2015 at earliest)
        channel_start = channel.published_at.date() if channel.published_at else date(2015, 1, 1)
        start = max(channel_start, date(2015, 1, 1))
        print(f"channel history: first run — fetching {start} → {today} (this may take a moment)")
    else:
        # incremental — just refresh the last 60 days to catch any youtube data revisions
        start = today - timedelta(days=60)
        print(f"channel history: incremental update {start} → {today}")

    # fetch core metrics + reach (impressions/ctr) in one batch of 180-day chunks
    try:
        daily_rows = await yt.get_channel_daily_stats(access_token, refresh_token, start, today)
    except Exception as e:
        print(f"channel history: core stats fetch failed, skipping: {e}")
        return

    if not daily_rows:
        print("channel history: no data returned from analytics api")
        return

    # fetch revenue separately — requires monetary scope, gracefully skipped if not granted
    revenue_by_date: dict[str, dict] = {}
    try:
        revenue_by_date = await yt.get_channel_daily_revenue(access_token, refresh_token, start, today)
        if revenue_by_date:
            print(f"channel history: revenue data available for {len(revenue_by_date)} days")
    except Exception as e:
        print(f"channel history: revenue skipped: {e}")

    # upsert every daily row — conflict on (channel_id, date) updates the existing row
    for row in daily_rows:
        day_str = row.get("day")
        if not day_str:
            continue

        day = date.fromisoformat(day_str)
        rev = revenue_by_date.get(day_str, {})

        # impressionsClickThroughRate from the api is a 0–1 decimal fraction
        # (the api docs say "expressed as a percentage" but actually returns a decimal)
        # we normalize: if it came back > 1 (old api behaviour), divide by 100
        raw_ctr = _safe_float(row.get("impressionsClickThroughRate"))
        if raw_ctr is not None and raw_ctr > 1:
            raw_ctr = raw_ctr / 100

        stmt = (
            pg_insert(ChannelDailyStats)
            .values(
                id=uuid.uuid4(),
                channel_id=channel.id,
                date=day,
                views=_safe_int(row.get("views")),
                estimated_minutes_watched=_safe_float(row.get("estimatedMinutesWatched")),
                average_view_duration_seconds=_safe_float(row.get("averageViewDuration")),
                likes=_safe_int(row.get("likes")),
                comments=_safe_int(row.get("comments")),
                subscribers_gained=_safe_int(row.get("subscribersGained")),
                subscribers_lost=_safe_int(row.get("subscribersLost")),
                impressions=_safe_int(row.get("impressions")),
                click_through_rate=raw_ctr,
                estimated_revenue=_safe_float(rev.get("estimatedRevenue")),
                fetched_at=_utcnow(),
            )
            .on_conflict_do_update(
                constraint="uq_channel_daily_stats_channel_date",
                set_={
                    "views": _safe_int(row.get("views")),
                    "estimated_minutes_watched": _safe_float(row.get("estimatedMinutesWatched")),
                    "average_view_duration_seconds": _safe_float(row.get("averageViewDuration")),
                    "likes": _safe_int(row.get("likes")),
                    "comments": _safe_int(row.get("comments")),
                    "subscribers_gained": _safe_int(row.get("subscribersGained")),
                    "subscribers_lost": _safe_int(row.get("subscribersLost")),
                    "impressions": _safe_int(row.get("impressions")),
                    "click_through_rate": raw_ctr,
                    "estimated_revenue": _safe_float(rev.get("estimatedRevenue")),
                    "fetched_at": _utcnow(),
                },
            )
        )
        await db.execute(stmt)

    print(f"channel history: saved {len(daily_rows)} daily rows")


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

    # ── step 4: fetch per-video analytics api data ───────────────────────────
    # wrapped in try/except — if analytics fail, the video sync still succeeds
    try:
        await _sync_analytics(db, access_token, refresh_token, channel)
    except Exception as exc:
        print(f"analytics sync skipped: {exc}")

    # ── step 5: fetch daily channel history for the charts page ──────────────
    # on first run this pulls the full channel history back to launch date.
    # on subsequent runs it only refreshes the last 60 days.
    try:
        await _sync_channel_history(db, access_token, refresh_token, channel)
    except Exception as exc:
        print(f"channel history sync skipped: {exc}")

    await db.commit()
    await db.refresh(channel)
    return channel
