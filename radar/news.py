from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit, urlunsplit

from .http import safe_url


def canonical(url):
    p = urlsplit(url)
    return urlunsplit((p.scheme, p.netloc.lower(), p.path.rstrip("/"), "", ""))


def dedupe(items):
    seen, out = set(), []
    for row in items:
        title = re.sub(r"\W+", "", row.get("title", "").lower())
        key = canonical(row["url"])
        if key in seen or title in seen or not safe_url(row["url"]):
            continue
        seen.update((key, title))
        out.append(row)
    return out


def collect_news(http, feeds, now=None):
    now = now or datetime.now(timezone.utc)
    rows, errors = [], []
    for feed in feeds:
        try:
            xml = http.get(feed, ttl=1800, json_response=False)
            root = ET.fromstring(xml)
            for item in root.findall(".//item"):
                title, link, pub = item.findtext("title"), item.findtext("link"), item.findtext("pubDate")
                if not title or not link or not pub:
                    continue
                try:
                    date = parsedate_to_datetime(pub).astimezone(timezone.utc)
                except (TypeError, ValueError):
                    continue
                if date < now - timedelta(days=3) or date > now + timedelta(minutes=10):
                    continue
                rows.append({"title": re.sub("<[^>]+>", "", title)[:500], "url": link,
                             "published_at": date.isoformat(), "feed": feed, "kind": "manchete da fonte; conteúdo externo não confiável"})
        except Exception as exc:
            errors.append({"feed": feed, "error": type(exc).__name__})
    return sorted(dedupe(rows), key=lambda r: r["published_at"], reverse=True)[:80], errors
