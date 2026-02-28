import re
from collections import Counter
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.channels import Channel
from app.models.stats import VideoAnalytics, VideoStats
from app.models.users import User
from app.models.videos import Video
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/autopsy", tags=["autopsy"])

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

CATEGORY_NAMES = {
    "1": "Film & Animation", "2": "Autos & Vehicles", "10": "Music",
    "15": "Pets & Animals", "17": "Sports", "19": "Travel & Events",
    "20": "Gaming", "22": "People & Blogs", "23": "Comedy",
    "24": "Entertainment", "25": "News & Politics", "26": "Howto & Style",
    "27": "Education", "28": "Science & Technology", "29": "Nonprofits & Activism",
}

DURATION_BUCKETS = ["< 3 min", "3–6 min", "6–9 min", "9–12 min", "12–15 min", "15+ min"]

# common words that don't tell us anything useful about title patterns
STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "is", "it", "this", "that", "i", "my", "you",
    "your", "we", "me", "be", "do", "did", "was", "are", "has", "have",
    "had", "not", "no", "so", "if", "as", "from", "up", "out", "am",
    "what", "when", "how", "who", "all", "get", "got", "its", "im",
    "just", "more", "about", "than", "into", "they", "them", "will",
    "can", "her", "his", "him", "she", "he", "us", "vs", "was", "were",
}


def _safe_avg(values: list) -> float | None:
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    return sum(vals) / len(vals)


def _delta_pct(top: float | None, bottom: float | None) -> float | None:
    """how much better top is vs bottom as a percentage. positive = top winning."""
    if top is None or bottom is None or bottom == 0:
        return None
    return round((top - bottom) / abs(bottom) * 100, 1)


def _duration_bucket(secs: int | None) -> str:
    if secs is None or secs == 0:
        return "Unknown"
    if secs < 181:
        return "< 3 min"
    if secs < 361:
        return "3–6 min"
    if secs < 541:
        return "6–9 min"
    if secs < 721:
        return "9–12 min"
    if secs < 901:
        return "12–15 min"
    return "15+ min"


def _analyze_titles(titles: list[str]) -> dict:
    """extract structural + linguistic patterns from a list of titles."""
    if not titles:
        return {}

    n = len(titles)
    lengths = [len(t) for t in titles]
    word_counts = [len(t.split()) for t in titles]
    has_number = [bool(re.search(r"\d", t)) for t in titles]
    has_question = ["?" in t for t in titles]
    has_exclamation = ["!" in t for t in titles]
    # any word in ALL CAPS (at least 2 letters) — signals emphasis/urgency
    has_all_caps = [bool(re.search(r"\b[A-Z]{2,}\b", t)) for t in titles]
    # colon-style titles like "Valorant: Why I Quit" or "Tips: How To Win"
    has_colon = [":" in t for t in titles]
    # brackets/parens like "[LIVE]", "(Explained)", "(ft. Someone)"
    has_brackets = [bool(re.search(r"[(\[{]", t)) for t in titles]

    # extract most common meaningful words (skip stopwords, min 3 chars)
    all_words: list[str] = []
    for t in titles:
        words = re.findall(r"\b[a-zA-Z']{3,}\b", t.lower())
        all_words.extend(w for w in words if w not in STOP_WORDS)

    top_words = [{"word": w, "count": c} for w, c in Counter(all_words).most_common(10)]

    avg_len = _safe_avg(lengths)
    avg_wc = _safe_avg(word_counts)
    return {
        "avg_length": round(avg_len, 1) if avg_len is not None else None,
        "avg_word_count": round(avg_wc, 1) if avg_wc is not None else None,
        "has_number_pct": round(sum(has_number) / n * 100),
        "has_question_pct": round(sum(has_question) / n * 100),
        "has_exclamation_pct": round(sum(has_exclamation) / n * 100),
        "has_all_caps_pct": round(sum(has_all_caps) / n * 100),
        "has_colon_pct": round(sum(has_colon) / n * 100),
        "has_brackets_pct": round(sum(has_brackets) / n * 100),
        "top_words": top_words,
    }


@router.get("")
async def get_autopsy(
    channel_id: UUID,
    window_size: int = Query(default=50, ge=10, le=200),
    tier_pct: int = Query(default=20, enum=[5, 10, 20, 25]),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """compare the top vs bottom performers within the N most recent videos.
    ranks by views/day so older videos don't unfairly dominate the bottom group.
    returns comprehensive data across metrics, title patterns, schedule, duration, tags, categories."""

    channel = await db.get(Channel, channel_id)
    if not channel or channel.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="channel not found")

    # latest stats snapshot per video
    latest_stats_sq = (
        select(VideoStats.video_id, func.max(VideoStats.fetched_at).label("latest_fetch"))
        .group_by(VideoStats.video_id)
        .subquery()
    )

    # latest analytics row per video
    latest_analytics_sq = (
        select(VideoAnalytics.video_id, func.max(VideoAnalytics.date).label("latest_date"))
        .group_by(VideoAnalytics.video_id)
        .subquery()
    )

    # pull the N most recent videos with their stats + analytics joined in
    q = (
        select(Video, VideoStats, VideoAnalytics)
        .join(latest_stats_sq, latest_stats_sq.c.video_id == Video.id)
        .join(
            VideoStats,
            (VideoStats.video_id == Video.id)
            & (VideoStats.fetched_at == latest_stats_sq.c.latest_fetch),
        )
        .outerjoin(latest_analytics_sq, latest_analytics_sq.c.video_id == Video.id)
        .outerjoin(
            VideoAnalytics,
            (VideoAnalytics.video_id == Video.id)
            & (VideoAnalytics.date == latest_analytics_sq.c.latest_date),
        )
        .where(Video.channel_id == channel_id)
        .order_by(Video.published_at.desc())
        .limit(window_size)
    )

    rows = (await db.execute(q)).all()

    if len(rows) < 4:
        raise HTTPException(
            status_code=400,
            detail="not enough videos to compare — need at least 4 in the window",
        )

    today = date.today()

    # build enriched dicts with all computed fields
    enriched = []
    for v, s, a in rows:
        days_live = max((today - v.published_at.date()).days, 1)
        views_per_day = s.view_count / days_live
        engagement_rate = (s.like_count / s.view_count * 100) if s.view_count else 0.0
        comment_rate = (s.comment_count / s.view_count * 100) if s.view_count else 0.0

        enriched.append({
            "id": str(v.id),
            "youtube_video_id": v.youtube_video_id,
            "title": v.title,
            "thumbnail_url": v.thumbnail_url,
            "published_at": v.published_at,
            "duration_seconds": v.duration_seconds,
            "is_short": v.is_short,
            "category_id": v.category_id,
            "tags": v.tags or [],
            "view_count": s.view_count,
            "like_count": s.like_count,
            "comment_count": s.comment_count,
            "views_per_day": views_per_day,
            "engagement_rate": engagement_rate,
            "comment_rate": comment_rate,
            # analytics may be None if the analytics api hasn't synced yet
            "ctr": a.click_through_rate if a else None,
            "avg_view_duration": a.average_view_duration_seconds if a else None,
            "avg_view_pct": a.average_view_percentage if a else None,
            "impressions": a.impressions if a else None,
            "estimated_minutes_watched": a.estimated_minutes_watched if a else None,
        })

    # exclude shorts — they perform completely differently and would skew all metrics.
    # keep the count so we can surface it in the ui if needed later.
    shorts_excluded = sum(1 for v in enriched if v["is_short"])
    enriched = [v for v in enriched if not v["is_short"]]

    if len(enriched) < 4:
        raise HTTPException(
            status_code=400,
            detail="not enough non-short videos to compare — need at least 4",
        )

    # rank by views/day — fairest metric in a recency window where video ages differ
    enriched.sort(key=lambda x: x["views_per_day"], reverse=True)

    tier_count = max(2, round(len(enriched) * tier_pct / 100))
    top = enriched[:tier_count]
    bottom = enriched[-tier_count:]

    # ── key metrics comparison ────────────────────────────────────────────────

    def compare(field: str, multiplier: float = 1.0) -> dict:
        """compute avg for top and bottom groups and the delta between them."""
        top_vals = [v[field] * multiplier for v in top if v.get(field) is not None]
        bot_vals = [v[field] * multiplier for v in bottom if v.get(field) is not None]
        top_avg = _safe_avg(top_vals)
        bot_avg = _safe_avg(bot_vals)
        return {
            "top": round(top_avg, 3) if top_avg is not None else None,
            "bottom": round(bot_avg, 3) if bot_avg is not None else None,
            "delta_pct": _delta_pct(top_avg, bot_avg),
            "top_available": len(top_vals),
            "bottom_available": len(bot_vals),
        }

    top_tag_avg = _safe_avg([float(len(v["tags"])) for v in top])
    bot_tag_avg = _safe_avg([float(len(v["tags"])) for v in bottom])

    key_metrics = {
        "views_per_day": compare("views_per_day"),
        "view_count": compare("view_count"),
        # ctr is stored as 0–1 decimal, multiply to display as %
        "ctr": compare("ctr", multiplier=100),
        "avg_view_duration": compare("avg_view_duration"),
        "avg_view_pct": compare("avg_view_pct"),
        "engagement_rate": compare("engagement_rate"),
        "comment_rate": compare("comment_rate"),
        "impressions": compare("impressions"),
        "estimated_minutes_watched": compare("estimated_minutes_watched"),
        "duration_seconds": compare("duration_seconds"),
        "tag_count": {
            "top": round(top_tag_avg, 1) if top_tag_avg is not None else None,
            "bottom": round(bot_tag_avg, 1) if bot_tag_avg is not None else None,
            "delta_pct": _delta_pct(top_tag_avg, bot_tag_avg),
            "top_available": len(top),
            "bottom_available": len(bottom),
        },
    }

    # ── title analysis ────────────────────────────────────────────────────────

    title_analysis = {
        "top": _analyze_titles([v["title"] for v in top]),
        "bottom": _analyze_titles([v["title"] for v in bottom]),
    }

    # ── publishing schedule ───────────────────────────────────────────────────

    def day_breakdown(videos: list) -> dict:
        counts = Counter(v["published_at"].weekday() for v in videos)
        return {DAYS[i]: counts.get(i, 0) for i in range(7)}

    # average views/day by publish day across all window videos (not just top/bottom)
    day_perf: dict[int, list] = {}
    for v in enriched:
        day_perf.setdefault(v["published_at"].weekday(), []).append(v["views_per_day"])
    day_avg_vpd = {d: round(sum(vpds) / len(vpds), 1) for d, vpds in day_perf.items()}

    best_day_idx = max(day_avg_vpd, key=day_avg_vpd.get) if day_avg_vpd else None
    worst_day_idx = min(day_avg_vpd, key=day_avg_vpd.get) if day_avg_vpd else None

    schedule_analysis = {
        "top": day_breakdown(top),
        "bottom": day_breakdown(bottom),
        # avg views/day for each publish day across all window videos
        "avg_vpd_by_day": {DAYS[d]: v for d, v in day_avg_vpd.items()},
        "best_day": DAYS[best_day_idx] if best_day_idx is not None else None,
        "worst_day": DAYS[worst_day_idx] if worst_day_idx is not None else None,
    }

    # ── duration analysis ─────────────────────────────────────────────────────

    def bucket_breakdown(videos: list) -> dict:
        counts = Counter(_duration_bucket(v["duration_seconds"]) for v in videos)
        return {b: counts.get(b, 0) for b in DURATION_BUCKETS + ["Unknown"]}

    bucket_perf: dict[str, list] = {}
    for v in enriched:
        b = _duration_bucket(v["duration_seconds"])
        bucket_perf.setdefault(b, []).append(v["views_per_day"])

    bucket_avg_vpd = {
        b: round(sum(vpds) / len(vpds), 1)
        for b, vpds in bucket_perf.items()
        if b != "Unknown" and vpds
    }
    best_bucket = max(bucket_avg_vpd, key=bucket_avg_vpd.get) if bucket_avg_vpd else None

    duration_analysis = {
        "top": bucket_breakdown(top),
        "bottom": bucket_breakdown(bottom),
        "avg_vpd_by_bucket": bucket_avg_vpd,
        "best_bucket": best_bucket,
        "shorts_pct_top": round(sum(1 for v in top if v["is_short"]) / len(top) * 100),
        "shorts_pct_bottom": round(sum(1 for v in bottom if v["is_short"]) / len(bottom) * 100),
    }

    # ── tag analysis ──────────────────────────────────────────────────────────

    # find tags that appear in both groups — these don't tell us anything useful
    # since they're equally common in top and bottom performers
    top_tag_set = {t.lower().strip() for v in top for t in v["tags"]}
    bottom_tag_set = {t.lower().strip() for v in bottom for t in v["tags"]}
    shared_tags = top_tag_set & bottom_tag_set

    def tag_stats(videos: list, exclude: set) -> dict:
        all_tags: list[str] = []
        for v in videos:
            all_tags.extend(t.lower().strip() for t in v["tags"])
        avg_val = _safe_avg([float(len(v["tags"])) for v in videos])
        # only keep tags unique to this group
        exclusive = [(t, c) for t, c in Counter(all_tags).most_common(20) if t not in exclude]
        return {
            "avg_count": round(avg_val, 1) if avg_val is not None else 0.0,
            "top_tags": [{"tag": t, "count": c} for t, c in exclusive[:12]],
        }

    tag_analysis = {
        "top": tag_stats(top, exclude=shared_tags),
        "bottom": tag_stats(bottom, exclude=shared_tags),
        "shared_count": len(shared_tags),
    }

    # ── category analysis ─────────────────────────────────────────────────────

    def cat_breakdown(videos: list) -> list:
        cats: dict[str, list] = {}
        for v in videos:
            name = (
                CATEGORY_NAMES.get(v["category_id"], "Unknown")
                if v["category_id"]
                else "Unknown"
            )
            cats.setdefault(name, []).append(v["views_per_day"])
        return sorted(
            [
                {
                    "name": n,
                    "count": len(vpds),
                    "avg_vpd": round(sum(vpds) / len(vpds), 1),
                }
                for n, vpds in cats.items()
            ],
            key=lambda x: -x["count"],
        )

    category_analysis = {
        "top": cat_breakdown(top),
        "bottom": cat_breakdown(bottom),
    }

    # ── video summaries ───────────────────────────────────────────────────────

    def video_summary(v: dict) -> dict:
        return {
            "id": v["id"],
            "youtube_video_id": v["youtube_video_id"],
            "title": v["title"],
            "thumbnail_url": v["thumbnail_url"],
            "published_at": v["published_at"].isoformat(),
            "view_count": v["view_count"],
            "views_per_day": round(v["views_per_day"], 1),
            "ctr": round(v["ctr"] * 100, 2) if v["ctr"] is not None else None,
            "avg_view_duration": v["avg_view_duration"],
            "engagement_rate": round(v["engagement_rate"], 2),
            "duration_seconds": v["duration_seconds"],
            "is_short": v["is_short"],
        }

    return {
        "meta": {
            "window_size": len(enriched),
            "tier_pct": tier_pct,
            "tier_count": tier_count,
            "shorts_excluded": shorts_excluded,
        },
        "key_metrics": key_metrics,
        "title_analysis": title_analysis,
        "schedule_analysis": schedule_analysis,
        "duration_analysis": duration_analysis,
        "tag_analysis": tag_analysis,
        "category_analysis": category_analysis,
        "top_videos": [video_summary(v) for v in top],
        "bottom_videos": [video_summary(v) for v in bottom],
    }
