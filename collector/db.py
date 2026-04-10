from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

# ICD_DB_PATH 環境変数でオーバーライド可能 (テスト用)
DB_PATH = Path(
    os.environ.get(
        "ICD_DB_PATH",
        str(Path(__file__).parent.parent / "data" / "collector.db"),
    )
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    name             TEXT NOT NULL UNIQUE,
    display_name     TEXT NOT NULL,
    category         TEXT NOT NULL,
    url              TEXT NOT NULL,
    fetcher_type     TEXT NOT NULL,
    active           INTEGER NOT NULL DEFAULT 1,
    user_agent       TEXT,
    last_fetched_at  TIMESTAMP,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS items (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id             INTEGER NOT NULL REFERENCES sources(id),
    external_id           TEXT NOT NULL,
    title                 TEXT NOT NULL,
    url                   TEXT NOT NULL,
    published_at          TIMESTAMP,
    raw_text              TEXT,
    summary               TEXT,
    fetched_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    prefilter_decision    TEXT,
    prefilter_decided_at  TIMESTAMP,
    prefilter_note        TEXT,
    UNIQUE(source_id, external_id)
);

CREATE INDEX IF NOT EXISTS idx_items_prefilter ON items(prefilter_decision, fetched_at DESC);
CREATE INDEX IF NOT EXISTS idx_items_source    ON items(source_id, fetched_at DESC);
"""


@contextmanager
def get_conn() -> Generator[sqlite3.Connection, None, None]:
    """トランザクション付きSQLite接続。例外時はロールバック。"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def apply_schema() -> None:
    """スキーマを適用する。既存テーブルはスキップ。"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    # executescript は内部で COMMIT を発行するため get_conn() の外で実行
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(SCHEMA)
    finally:
        conn.close()


def insert_item(conn: sqlite3.Connection, source_id: int, item: dict) -> bool:
    """アイテムを挿入する。重複の場合は False を返す。"""
    try:
        conn.execute(
            """INSERT INTO items
               (source_id, external_id, title, url, published_at, summary, raw_text)
               VALUES (:source_id, :external_id, :title, :url, :published_at, :summary, :raw_text)""",
            {
                "source_id": source_id,
                "external_id": item["external_id"],
                "title": item["title"],
                "url": item["url"],
                "published_at": item.get("published_at"),
                "summary": item.get("summary"),
                "raw_text": item.get("raw_text"),
            },
        )
        return True
    except sqlite3.IntegrityError:
        return False


def update_source_fetched(conn: sqlite3.Connection, source_id: int) -> None:
    conn.execute(
        "UPDATE sources SET last_fetched_at = CURRENT_TIMESTAMP WHERE id = ?",
        (source_id,),
    )


def update_prefilter(
    conn: sqlite3.Connection,
    item_id: int,
    decision: str,
    note: str | None = None,
) -> None:
    conn.execute(
        """UPDATE items
           SET prefilter_decision = ?, prefilter_decided_at = CURRENT_TIMESTAMP, prefilter_note = ?
           WHERE id = ?""",
        (decision, note or None, item_id),
    )
