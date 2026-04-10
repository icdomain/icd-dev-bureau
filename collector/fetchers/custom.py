"""個別対応が必要なソース用フェッチャー。

現在の実装:
- PwcFetcher: Papers with Code Trending (REST API)
"""
from __future__ import annotations

import httpx
from loguru import logger

from .base import BaseFetcher, FetchedItem

USER_AGENT = "icd-collector/0.1 (+https://icdomain.github.io/)"
TIMEOUT = 30


class PwcFetcher(BaseFetcher):
    """HuggingFace Daily Papers (旧 Papers with Code) からトレンド論文を取得する。

    PWC は HuggingFace に統合済み。
    API: https://huggingface.co/api/daily_papers
    """

    def fetch(self) -> list[FetchedItem]:
        resp = httpx.get(
            "https://huggingface.co/api/daily_papers",
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT,
            follow_redirects=True,
        )
        resp.raise_for_status()
        data = resp.json()

        items: list[FetchedItem] = []
        for entry in data:
            paper = entry.get("paper") or entry
            arxiv_id: str = paper.get("id") or ""
            if not arxiv_id:
                continue

            title: str = (paper.get("title") or "").strip()
            if not title:
                continue

            url = f"https://huggingface.co/papers/{arxiv_id}"
            abstract: str | None = paper.get("abstract") or None
            if abstract:
                abstract = abstract[:2000]

            published_at: str | None = entry.get("publishedAt") or paper.get("publishedAt") or None

            items.append(
                FetchedItem(
                    external_id=arxiv_id,
                    title=title,
                    url=url,
                    published_at=published_at,
                    summary=abstract,
                    raw_text=None,
                )
            )

        return items
