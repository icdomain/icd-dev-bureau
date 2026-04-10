"""全ソースからアイテムを収集してDBに保存する。

Usage:
    python -m collector.fetch
"""
from __future__ import annotations

import time

from loguru import logger

from .db import get_conn, insert_item, update_source_fetched
from .fetchers.custom import PwcFetcher
from .fetchers.hf_api import HfModelsFetcher, HfSpacesFetcher
from .fetchers.rss import RssFetcher

FETCHER_MAP = {
    "rss": RssFetcher,
    "api_hf_models": HfModelsFetcher,
    "api_hf_spaces": HfSpacesFetcher,
    "api_pwc": PwcFetcher,
}

# ソース間の最小待機時間 (秒)
INTER_SOURCE_DELAY = 1.0


def fetch_all() -> None:
    with get_conn() as conn:
        sources = [
            dict(row)
            for row in conn.execute("SELECT * FROM sources WHERE active = 1").fetchall()
        ]

    logger.info(f"Starting fetch for {len(sources)} active source(s)")

    total_new = 0
    errors = 0

    for source in sources:
        fetcher_cls = FETCHER_MAP.get(source["fetcher_type"])
        if fetcher_cls is None:
            logger.warning(f"[{source['name']}] Unknown fetcher_type: {source['fetcher_type']}")
            continue

        try:
            fetcher = fetcher_cls(source)
            items = fetcher.fetch()

            new_count = 0
            with get_conn() as conn:
                for item in items:
                    if insert_item(conn, source["id"], item):
                        new_count += 1
                update_source_fetched(conn, source["id"])

            total_new += new_count
            logger.info(
                f"[{source['name']}] fetched={len(items)} new={new_count}"
            )

        except Exception as exc:
            errors += 1
            logger.error(f"[{source['name']}] FAILED: {exc}")

        time.sleep(INTER_SOURCE_DELAY)

    logger.info(f"Fetch complete. total_new={total_new} errors={errors}")


if __name__ == "__main__":
    fetch_all()
