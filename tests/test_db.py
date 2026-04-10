"""DB操作の基本テスト。"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest


@pytest.fixture()
def tmp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """テスト用の一時DBパスを設定する。"""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("ICD_DB_PATH", str(db_path))

    # モジュールを再インポートしてDB_PATHを更新
    import importlib
    import collector.db as db_mod
    importlib.reload(db_mod)

    from collector.db import apply_schema
    apply_schema()

    yield db_mod

    # クリーンアップ (tmp_path は pytest が自動削除)


def _insert_source(conn: sqlite3.Connection, name: str = "test_source") -> int:
    cur = conn.execute(
        "INSERT INTO sources (name, display_name, category, url, fetcher_type) VALUES (?, ?, ?, ?, ?)",
        (name, "Test Source", "vendor", "https://example.com/rss", "rss"),
    )
    conn.commit()
    return cur.lastrowid


def test_schema_creates_tables(tmp_db):
    with tmp_db.get_conn() as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert "sources" in tables
    assert "items" in tables


def test_insert_source(tmp_db):
    conn = sqlite3.connect(tmp_db.DB_PATH)
    source_id = _insert_source(conn)
    conn.close()

    with tmp_db.get_conn() as conn:
        row = conn.execute("SELECT * FROM sources WHERE id = ?", (source_id,)).fetchone()
    assert row is not None
    assert row["name"] == "test_source"


def test_insert_item_new(tmp_db):
    conn = sqlite3.connect(tmp_db.DB_PATH)
    source_id = _insert_source(conn)
    conn.close()

    item = {
        "external_id": "https://example.com/post/1",
        "title": "Test Post",
        "url": "https://example.com/post/1",
        "published_at": None,
        "summary": "Test summary",
        "raw_text": None,
    }

    with tmp_db.get_conn() as conn:
        result = tmp_db.insert_item(conn, source_id, item)

    assert result is True


def test_insert_item_duplicate(tmp_db):
    conn = sqlite3.connect(tmp_db.DB_PATH)
    source_id = _insert_source(conn)
    conn.close()

    item = {
        "external_id": "https://example.com/post/1",
        "title": "Test Post",
        "url": "https://example.com/post/1",
        "published_at": None,
        "summary": None,
        "raw_text": None,
    }

    with tmp_db.get_conn() as conn:
        first = tmp_db.insert_item(conn, source_id, item)

    with tmp_db.get_conn() as conn:
        second = tmp_db.insert_item(conn, source_id, item)

    assert first is True
    assert second is False


def test_update_prefilter(tmp_db):
    conn = sqlite3.connect(tmp_db.DB_PATH)
    source_id = _insert_source(conn)
    conn.close()

    item = {
        "external_id": "ext-001",
        "title": "Some Article",
        "url": "https://example.com/article",
        "published_at": None,
        "summary": None,
        "raw_text": None,
    }

    with tmp_db.get_conn() as conn:
        tmp_db.insert_item(conn, source_id, item)
        item_id = conn.execute("SELECT id FROM items WHERE external_id = 'ext-001'").fetchone()[0]

    with tmp_db.get_conn() as conn:
        tmp_db.update_prefilter(conn, item_id, "accept", "good article")

    with tmp_db.get_conn() as conn:
        row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()

    assert row["prefilter_decision"] == "accept"
    assert row["prefilter_note"] == "good article"
    assert row["prefilter_decided_at"] is not None
