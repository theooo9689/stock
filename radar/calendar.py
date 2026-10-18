from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

BLS_CALENDAR = "https://www.bls.gov/schedule/news_release/bls.ics"


def parse_calendar(text, now):
    """Read dated VEVENTs; do not infer dates from prose or floating local times."""
    text = re.sub(r"\r?\n[ \t]", "", text)
    events = []
    for block in text.split("BEGIN:VEVENT")[1:]:
        fields = {}
        for line in block.split("END:VEVENT")[0].splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                fields[k] = v
        start = next((k for k in fields if k.startswith("DTSTART")), None)
        if not start or not fields.get("SUMMARY"):
            continue
        value = fields[start]
        try:
            if value.endswith("Z"):
                when = datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
            elif "TZID=" in start:
                zone = start.split("TZID=", 1)[1].strip('"')
                zone = {"US-Eastern": "America/New_York", "Eastern Standard Time": "America/New_York"}.get(zone, zone)
                when = datetime.strptime(value, "%Y%m%dT%H%M%S").replace(tzinfo=ZoneInfo(zone)).astimezone(timezone.utc)
            else:
                continue
        except (ValueError, KeyError):
            continue
        if now <= when <= now + timedelta(days=7):
            title = fields["SUMMARY"].replace(r"\,", ",").replace(r"\n", " ")
            events.append({"fact": title, "source_url": BLS_CALENDAR, "published_at": when.isoformat()})
    return sorted(events, key=lambda e: e["published_at"])


def official_events(http, now=None):
    now = now or datetime.now(timezone.utc)
    try:
        return parse_calendar(http.get(BLS_CALENDAR, ttl=21600, json_response=False), now), []
    except Exception as exc:
        return [], [f"Calendário oficial BLS indisponível ({type(exc).__name__})"]
