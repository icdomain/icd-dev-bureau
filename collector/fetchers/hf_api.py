from __future__ import annotations

import time

import httpx
from loguru import logger

from .base import BaseFetcher, FetchedItem

USER_AGENT = "icd-collector/0.1 (+https://icdomain.github.io/)"
TIMEOUT = 30
HF_BASE = "https://huggingface.co/api"
TRENDING_LIMIT = 30
MAX_RETRIES = 4


def _fetch_with_backoff(url: str, params: dict) -> list[dict]:
    """指数バックオフ付きGET。429時にリトライ。"""
    for attempt in range(MAX_RETRIES):
        try:
            resp = httpx.get(
                url,
                params=params,
                headers={"User-Agent": USER_AGENT},
                timeout=TIMEOUT,
            )
            if resp.status_code == 429:
                wait = 2**attempt
                logger.warning(f"HF API rate limited (attempt {attempt+1}), waiting {wait}s")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                wait = 2**attempt
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("HF API rate limit exceeded after retries")


class HfModelsFetcher(BaseFetcher):
    def fetch(self) -> list[FetchedItem]:
        # sort=likes7d: 直近7日のいいね数順 (trending は HF Hub API で非対応)
        data = _fetch_with_backoff(
            f"{HF_BASE}/models",
            {"sort": "likes7d", "limit": TRENDING_LIMIT},
        )

        items: list[FetchedItem] = []
        for model in data:
            model_id: str = model.get("modelId") or model.get("id") or ""
            if not model_id:
                continue

            description: str | None = None
            card_data = model.get("cardData") or {}
            if isinstance(card_data, dict):
                description = card_data.get("description") or None

            items.append(
                FetchedItem(
                    external_id=model_id,
                    title=model_id,
                    url=f"https://huggingface.co/{model_id}",
                    published_at=model.get("createdAt"),
                    summary=description,
                    raw_text=None,
                )
            )

        return items


class HfSpacesFetcher(BaseFetcher):
    def fetch(self) -> list[FetchedItem]:
        # sort=likes7d: 直近7日のいいね数順
        data = _fetch_with_backoff(
            f"{HF_BASE}/spaces",
            {"sort": "likes7d", "limit": TRENDING_LIMIT},
        )

        items: list[FetchedItem] = []
        for space in data:
            space_id: str = space.get("id") or ""
            if not space_id:
                continue

            items.append(
                FetchedItem(
                    external_id=space_id,
                    title=space_id,
                    url=f"https://huggingface.co/spaces/{space_id}",
                    published_at=space.get("createdAt"),
                    summary=None,
                    raw_text=None,
                )
            )

        return items
