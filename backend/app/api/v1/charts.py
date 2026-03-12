import json
from uuid import UUID

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.channels import Channel
from app.models.stats import ChannelDailyStats
from app.models.users import User
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/charts", tags=["charts"])


@router.get("/channel")
async def get_channel_chart_data(
    request: Request,
    channel_id: UUID,
    granularity: str = Query("daily", pattern="^(daily|weekly|monthly)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """return daily/weekly/monthly channel performance data for the charts page.
    pulls from channel_daily_stats which is populated by the sync job."""

    # verify the requesting user actually owns this channel
    channel = await db.scalar(
        select(Channel).where(Channel.id == channel_id, Channel.user_id == current_user.id)
    )
    if not channel:
        raise HTTPException(status_code=404, detail="channel not found")

    # check redis cache first — no point re-querying if nothing has changed
    redis = request.app.state.redis
    cache_key = f"charts:{channel_id}:{granularity}"
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    # build the period grouping expression based on requested granularity
    if granularity == "weekly":
        period_expr = func.date_trunc("week", ChannelDailyStats.date).cast(sa.Date)
    elif granularity == "monthly":
        period_expr = func.date_trunc("month", ChannelDailyStats.date).cast(sa.Date)
    else:
        period_expr = ChannelDailyStats.date

    # aggregate all daily rows into the requested time buckets
    # ctr is weighted by impressions so high-impression days count more
    # rpm is derived from revenue / views * 1000 (no rpm column in channel_daily_stats)
    stmt = (
        select(
            period_expr.label("period"),
            func.sum(func.coalesce(ChannelDailyStats.views, 0)).label("views"),
            func.sum(func.coalesce(ChannelDailyStats.likes, 0)).label("likes"),
            func.sum(func.coalesce(ChannelDailyStats.comments, 0)).label("comments"),
            func.sum(func.coalesce(ChannelDailyStats.subscribers_gained, 0)).label("subscribers_gained"),
            func.sum(func.coalesce(ChannelDailyStats.impressions, 0)).label("impressions"),
            func.sum(func.coalesce(ChannelDailyStats.estimated_minutes_watched, 0)).label("watch_time_minutes"),
            func.sum(func.coalesce(ChannelDailyStats.estimated_revenue, 0)).label("revenue"),
            # weighted average ctr by impressions — converts 0–1 fraction to 0–100 percentage
            (
                func.sum(
                    func.coalesce(ChannelDailyStats.click_through_rate, 0)
                    * func.coalesce(ChannelDailyStats.impressions, 0)
                )
                / func.nullif(func.sum(func.coalesce(ChannelDailyStats.impressions, 0)), 0)
                * 100
            ).label("ctr"),
            # rpm = revenue per 1000 views for the period
            (
                func.sum(func.coalesce(ChannelDailyStats.estimated_revenue, 0))
                / func.nullif(func.sum(func.coalesce(ChannelDailyStats.views, 0)), 0)
                * 1000
            ).label("rpm"),
            # simple average of daily avg view durations within the period
            func.avg(ChannelDailyStats.average_view_duration_seconds).label("avg_view_duration"),
        )
        .where(ChannelDailyStats.channel_id == channel_id)
        .group_by(period_expr)
        .order_by(period_expr)
    )

    rows = (await db.execute(stmt)).all()

    if not rows:
        empty = {m: [] for m in ["views", "likes", "comments", "subscribers_gained", "impressions", "watch_time_minutes", "revenue", "ctr", "rpm", "avg_view_duration"]}
        result = {"dates": [], "metrics": empty, "date_range": None, "granularity": granularity}
        return result

    dates = [row.period.isoformat() for row in rows]

    # null out ctr/rpm/revenue for periods with no impressions/views/revenue data
    # so the frontend renders a gap instead of a fake 0
    def nullable_ctr(row) -> float | None:
        if row.ctr is None:
            return None
        raw = float(row.ctr)
        # if all impressions were 0 the weighted avg formula returns null; treat 0 as no data too
        total_imp = sum(
            int(r.impressions or 0) for r in rows
            if r.period == row.period
        )
        return round(raw, 3) if total_imp > 0 else None

    metrics = {
        "views":              [int(row.views or 0) for row in rows],
        "likes":              [int(row.likes or 0) for row in rows],
        "comments":           [int(row.comments or 0) for row in rows],
        "subscribers_gained": [int(row.subscribers_gained or 0) for row in rows],
        "impressions":        [int(row.impressions or 0) for row in rows],
        "watch_time_minutes": [round(float(row.watch_time_minutes or 0), 1) for row in rows],
        "revenue":            [round(float(row.revenue or 0), 2) for row in rows],
        "ctr":                [round(float(row.ctr), 3) if row.ctr is not None else None for row in rows],
        "rpm":                [round(float(row.rpm), 2) if row.rpm is not None else None for row in rows],
        "avg_view_duration":  [round(float(row.avg_view_duration), 1) if row.avg_view_duration is not None else None for row in rows],
    }

    result = {
        "dates": dates,
        "metrics": metrics,
        "date_range": {"min": dates[0], "max": dates[-1]},
        "granularity": granularity,
    }

    # cache for 30 minutes — data only changes when a sync runs
    await redis.setex(cache_key, 1800, json.dumps(result))
    return result
