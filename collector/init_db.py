"""DBスキーマ作成とソース初期登録。

Usage:
    python -m collector.init_db
"""
from __future__ import annotations

from pathlib import Path

import yaml
from loguru import logger

from .db import apply_schema, get_conn


def _register_sources(sources: list[dict]) -> None:
    with get_conn() as conn:
        inserted = 0
        updated = 0
        for src in sources:
            active = int(src.get("active", True))
            # 新規挿入
            user_agent = src.get("user_agent") or None
            result = conn.execute(
                """INSERT OR IGNORE INTO sources
                   (name, display_name, category, url, fetcher_type, active, user_agent)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    src["name"],
                    src["display_name"],
                    src["category"],
                    src["url"],
                    src["fetcher_type"],
                    active,
                    user_agent,
                ),
            )
            if result.rowcount:
                inserted += 1
                logger.debug(f"  registered: {src['name']}")
            else:
                # 既存レコードは url / active / user_agent を同期する
                upd = conn.execute(
                    """UPDATE sources SET url = ?, active = ?, user_agent = ?
                       WHERE name = ?
                         AND (url != ? OR active != ?
                              OR COALESCE(user_agent,'') != COALESCE(?,''))""",
                    (
                        src["url"], active, user_agent, src["name"],
                        src["url"], active, user_agent,
                    ),
                )
                if upd.rowcount:
                    updated += 1
                    logger.debug(f"  synced: {src['name']}")

    logger.info(f"Sources: {inserted} inserted, {updated} active-flag updated")


def init_db() -> None:
    logger.info("Initializing DB ...")
    apply_schema()
    logger.info("Schema applied")

    sources_path = Path(__file__).parent / "sources.yaml"
    with open(sources_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    _register_sources(data["sources"])
    logger.info("Done.")


if __name__ == "__main__":
    init_db()
