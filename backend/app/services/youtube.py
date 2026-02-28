import asyncio
import csv
import io
from datetime import date
from functools import partial

import httpx
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


def _build_reporting_client(access_token: str, refresh_token: str | None):
    """build the youtube reporting v1 api client — used for bulk csv report downloads."""
    creds = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
    )
    return build("youtubereporting", "v1", credentials=creds)


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
    # these three metrics are confirmed to work with dimensions=video
    # averageViewPercentage is excluded — not supported in this report type
    metrics = "views,estimatedMinutesWatched,averageViewDuration"

    results: dict[str, dict] = {}
    start_index = 1

    while True:
        response = await _run(
            analytics.reports().query(
                ids="channel==MINE",
                startDate="2020-01-01",
                endDate=today,
                dimensions="video",
                metrics=metrics,
                sort="-views",
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


async def ensure_reach_job(access_token: str, refresh_token: str | None) -> str:
    """find an existing reach reporting job or create one if none exists.
    this only needs to happen once ever — after that google keeps generating
    daily csv reports automatically and we just download them on each sync."""
    reporting = _build_reporting_client(access_token, refresh_token)

    # check if we already have a job running for this report type
    jobs_resp = await _run(reporting.jobs().list().execute)
    for job in jobs_resp.get("jobs", []):
        if job.get("reportTypeId") == "channel_reach_basic_a1":
            return job["id"]

    # no job found — create one (google will start generating daily csvs from now on,
    # plus backfill up to ~60 days of historical data)
    new_job = await _run(
        reporting.jobs().create(
            body={"reportTypeId": "channel_reach_basic_a1", "name": "viewpilot reach"}
        ).execute
    )
    return new_job["id"]


async def download_reach_reports(
    access_token: str, refresh_token: str | None, job_id: str
) -> list[dict]:
    """download all available reach report csv files for the job and return parsed rows.
    each row is a dict with video_id, impressions, and ctr for a single day.
    we aggregate these in sync.py to get per-video totals."""

    # build creds directly so we can read back the token after any auto-refresh
    creds = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
    )
    reporting = build("youtubereporting", "v1", credentials=creds)

    # get the list of available report files (google generates one per day)
    reports_resp = await _run(
        reporting.jobs().reports().list(jobId=job_id).execute
    )
    reports = reports_resp.get("reports", [])
    if not reports:
        return []

    all_rows = []
    # use creds.token here — the api call above may have silently refreshed it,
    # so the original access_token variable could already be expired and wrong
    auth_headers = {"Authorization": f"Bearer {creds.token}"}

    async with httpx.AsyncClient(timeout=30) as client:
        for report in reports:
            download_url = report.get("downloadUrl")
            if not download_url:
                continue

            resp = await client.get(download_url, headers=auth_headers)
            if resp.status_code != 200:
                print(f"reach reports: csv download failed with status {resp.status_code}")
                continue

            # strip utf-8 bom if present, then parse csv
            text = resp.text.lstrip("\ufeff")
            reader = csv.DictReader(io.StringIO(text))

            for row in reader:
                video_id = row.get("video_id", "").strip()
                if not video_id:
                    continue  # skip channel-level aggregate rows
                try:
                    impressions = int(float(row.get("video_thumbnail_impressions") or 0))
                    ctr = float(row.get("video_thumbnail_impressions_ctr") or 0)
                    all_rows.append({
                        "video_id": video_id,
                        "impressions": impressions,
                        "ctr": ctr,
                    })
                except (ValueError, TypeError):
                    continue

    return all_rows
