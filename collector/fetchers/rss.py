from __future__ import annotations

import html
import re
from datetime import datetime, timezone

import feedparser
import httpx
from loguru import logger

from .base import BaseFetcher, FetchedItem

USER_AGENT = "icd-collector/0.1 (+https://icdomain.github.io/)"
TIMEOUT = 30
SUMMARY_MAX = 2000


def _strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()


def _parse_date(entry: dict) -> str | None:
    for field in ("published_parsed", "updated_parsed"):
        parsed = entry.get(field)
        if parsed:
            try:
                return datetime(*parsed[:6], tzinfo=timezone.utc).isoformat()
            except Exception:
                pass
    return None


class RssFetcher(BaseFetcher):
    def fetch(self) -> list[FetchedItem]:
        resp = httpx.get(
            self.source["url"],
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT,
            follow_redirects=True,
        )
        resp.raise_for_status()

        feed = feedparser.parse(resp.content)

        if feed.bozo and not feed.entries:
            raise ValueError(f"Invalid feed: {feed.bozo_exception}")

        if feed.bozo:
            logger.debug(
                f"[{self.source['name']}] bozo feed (but has entries): {feed.bozo_exception}"
            )

        items: list[FetchedItem] = []
        for entry in feed.entries:
            external_id: str = entry.get("id") or entry.get("link") or ""
            if not external_id:
                continue

            title: str = (entry.get("title") or "").strip()
            if not title:
                continue

            url: str = entry.get("link") or external_id

            raw_summary = entry.get("summary") or entry.get("description") or ""
            summary: str | None = None
            if raw_summary:
                summary = _strip_html(raw_summary)[:SUMMARY_MAX] or None

            items.append(
                FetchedItem(
                    external_id=external_id,
                    title=title,
                    url=url,
                    published_at=_parse_date(entry),
                    summary=summary,
                    raw_text=None,
                )
            )

        return items
