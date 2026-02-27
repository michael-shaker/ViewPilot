import asyncio
from datetime import date
from functools import partial

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.config import settings


def _build_client(access_token: str, refresh_token: str | None):
    """build a google api client using the user's stored oauth tokens."""
    creds = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
    )
    return build("youtube", "v3", credentials=creds)


def _build_analytics_client(access_token: str, refresh_token: str | None):
    """build the youtube analytics v2 api client — separate from the data api."""
    creds = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
    )
    return build("youtubeAnalytics", "v2", credentials=creds)


async def _run(func, *args, **kwargs):
    """run a synchronous google api call in a thread so it doesn't block the async server."""
    return await asyncio.to_thread(partial(func, *args, **kwargs))


async def get_channel_info(access_token: str, refresh_token: str | None) -> dict:
    """fetch the user's youtube channel info — name, subscriber count, uploads playlist id etc."""
    youtube = _build_client(access_token, refresh_token)
    response = await _run(
        youtube.channels().list(
            part="snippet,statistics,contentDetails",
            mine=True,
        ).execute
    )
    items = response.get("items", [])
    if not items:
        raise ValueError("no youtube channel found for this account")
    return items[0]


async def get_all_video_ids(
    access_token: str, refresh_token: str | None, uploads_playlist_id: str
) -> list[str]:
    """page through the uploads playlist and collect every video id on the channel."""
    youtube = _build_client(access_token, refresh_token)
    video_ids = []
    next_page_token = None

    while True:
        response = await _run(
            youtube.playlistItems().list(
                part="contentDetails",
                playlistId=uploads_playlist_id,
                maxResults=50,
                pageToken=next_page_token,
            ).execute
        )
        for item in response.get("items", []):
            video_ids.append(item["contentDetails"]["videoId"])

        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break

    return video_ids


async def get_videos_batch(
    access_token: str, refresh_token: str | None, video_ids: list[str]
) -> list[dict]:
    """fetch full metadata + stats for up to 50 videos at a time."""
    youtube = _build_client(access_token, refresh_token)
    response = await _run(
        youtube.videos().list(
            part="snippet,statistics,contentDetails",
            id=",".join(video_ids),
            maxResults=50,
        ).execute
    )
    return response.get("items", [])


async def get_channel_analytics(
    access_token: str, refresh_token: str | None
) -> dict[str, dict]:
    """pull lifetime analytics for every video on the channel in 1-2 api calls.
    returns a dict keyed by youtube video id with ctr, impressions, avg watch time etc."""
    analytics = _build_analytics_client(access_token, refresh_token)
    today = date.today().isoformat()
    metrics = ",".join([
        "views",
        "estimatedMinutesWatched",
        "averageViewDuration",
        "averageViewPercentage",
        "impressions",
        "impressionsClickThroughRate",
        "likes",
        "comments",
        "shares",
        "subscribersGained",
        "subscribersLost",
    ])

    results: dict[str, dict] = {}
    start_index = 1

    while True:
        response = await _run(
            analytics.reports().query(
                ids="channel==MINE",
                startDate="2010-01-01",
                endDate=today,
                dimensions="video",
                metrics=metrics,
                maxResults=200,
                startIndex=start_index,
            ).execute
        )

        rows = response.get("rows") or []
        if not rows:
            break

        # map column positions to names so we don't rely on order
        headers = [h["name"] for h in response["columnHeaders"]]
        for row in rows:
            yt_vid_id = row[0]  # first column is always the video dimension
            results[yt_vid_id] = dict(zip(headers, row))

        row_count = response.get("rowCount", 0)
        fetched = start_index - 1 + len(rows)
        if fetched >= row_count:
            break
        start_index += 200

    return results
