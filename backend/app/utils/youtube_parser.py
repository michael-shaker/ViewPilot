import re


def parse_duration(iso_duration: str) -> int:
    """convert youtube's iso 8601 duration string to total seconds.
    e.g. PT4M13S -> 253, PT1H2M30S -> 3750, PT45S -> 45"""
    if not iso_duration:
        return 0
    pattern = re.compile(
        r"PT(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?"
    )
    match = pattern.match(iso_duration)
    if not match:
        return 0
    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes") or 0)
    seconds = int(match.group("seconds") or 0)
    return hours * 3600 + minutes * 60 + seconds


def best_thumbnail(thumbnails: dict) -> str | None:
    """pick the highest quality thumbnail url available."""
    for quality in ("maxres", "standard", "high", "medium", "default"):
        if quality in thumbnails:
            return thumbnails[quality]["url"]
    return None
