"""ICD Prefilter UI

Usage:
    streamlit run ui/prefilter.py
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import streamlit as st

DB_PATH = Path(
    os.environ.get(
        "ICD_DB_PATH",
        str(Path(__file__).parent.parent / "data" / "collector.db"),
    )
)

PAGE_SIZE = 20

CATEGORY_COLORS: dict[str, str] = {
    "vendor": "#1E90FF",
    "independent": "#2ECC71",
    "platform": "#F39C12",
}

DECISION_LABELS: dict[str, str] = {
    "accept": "採択済み",
    "reject": "見送り済み",
    "defer": "保留済み",
}


# ── DB helpers ────────────────────────────────────────────────────────────────

def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def load_sources() -> list[dict]:
    conn = _conn()
    rows = conn.execute(
        "SELECT id, name, display_name, category FROM sources ORDER BY category, display_name"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def count_by_decision() -> dict[str, int]:
    conn = _conn()
    rows = conn.execute(
        """SELECT COALESCE(prefilter_decision, 'pending') AS dec, COUNT(*) AS cnt
           FROM items GROUP BY dec"""
    ).fetchall()
    conn.close()
    result = {"pending": 0, "accept": 0, "reject": 0, "defer": 0}
    for row in rows:
        if row["dec"] in result:
            result[row["dec"]] = row["cnt"]
    return result


def load_items(
    source_ids: list[int] | None,
    date_from,
    date_to,
    decision_filter: str,
    offset: int,
    limit: int,
) -> tuple[list[dict], int]:
    conn = _conn()
    conditions: list[str] = []
    params: list = []

    if decision_filter == "pending":
        conditions.append("i.prefilter_decision IS NULL")
    elif decision_filter != "all":
        conditions.append("i.prefilter_decision = ?")
        params.append(decision_filter)

    if source_ids:
        placeholders = ",".join("?" * len(source_ids))
        conditions.append(f"i.source_id IN ({placeholders})")
        params.extend(source_ids)

    if date_from:
        conditions.append("DATE(i.fetched_at) >= ?")
        params.append(str(date_from))

    if date_to:
        conditions.append("DATE(i.fetched_at) <= ?")
        params.append(str(date_to))

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    total: int = conn.execute(
        f"SELECT COUNT(*) FROM items i {where}", params
    ).fetchone()[0]

    rows = conn.execute(
        f"""SELECT i.*, s.display_name AS source_name, s.category
            FROM items i JOIN sources s ON i.source_id = s.id
            {where}
            ORDER BY i.fetched_at DESC
            LIMIT ? OFFSET ?""",
        params + [limit, offset],
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows], total


def update_decision(item_id: int, decision: str, note: str) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """UPDATE items
               SET prefilter_decision = ?,
                   prefilter_decided_at = CURRENT_TIMESTAMP,
                   prefilter_note = ?
               WHERE id = ?""",
            (decision, note.strip() or None, item_id),
        )


# ── UI ────────────────────────────────────────────────────────────────────────

st.set_page_config(page_title="ICD Prefilter", layout="wide", page_icon="🔍")

if not DB_PATH.exists():
    st.error(f"DBが見つかりません: `{DB_PATH}`\n\n先に `python -m collector.init_db` を実行してください。")
    st.stop()

st.title("ICD Prefilter")

# session state
if "page" not in st.session_state:
    st.session_state.page = 0

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("フィルタ")

    try:
        sources = load_sources()
    except Exception as e:
        st.error(f"ソース読み込みエラー: {e}")
        sources = []

    source_options = {s["display_name"]: s["id"] for s in sources}
    selected_display = st.multiselect("ソース", list(source_options.keys()))
    selected_source_ids = [source_options[d] for d in selected_display] or None

    decision_filter = st.selectbox(
        "ステータス",
        ["pending", "accept", "reject", "defer", "all"],
        format_func=lambda x: {
            "pending": "未処理",
            "accept": "採択済み",
            "reject": "見送り済み",
            "defer": "保留済み",
            "all": "すべて",
        }[x],
    )

    st.divider()
    date_from = st.date_input("収集日 From", value=None)
    date_to = st.date_input("収集日 To", value=None)

    if st.button("フィルタをリセット", use_container_width=True):
        st.session_state.page = 0
        st.rerun()

# ── Metrics ───────────────────────────────────────────────────────────────────
try:
    counts = count_by_decision()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("未処理", counts["pending"])
    c2.metric("採択", counts["accept"])
    c3.metric("見送り", counts["reject"])
    c4.metric("保留", counts["defer"])
except Exception:
    pass

st.divider()

# ── Item list ─────────────────────────────────────────────────────────────────
try:
    items, total = load_items(
        selected_source_ids,
        date_from,
        date_to,
        decision_filter,
        offset=st.session_state.page * PAGE_SIZE,
        limit=PAGE_SIZE,
    )
except Exception as e:
    st.error(f"アイテム読み込みエラー: {e}")
    items, total = [], 0

if not items:
    st.info("表示するアイテムがありません。")
else:
    for item in items:
        category = item.get("category", "platform")
        color = CATEGORY_COLORS.get(category, "#888888")
        item_id: int = item["id"]
        note_key = f"note_{item_id}"

        with st.container(border=True):
            col_main, col_actions = st.columns([3, 1])

            with col_main:
                badge_html = (
                    f'<span style="background:{color};color:white;padding:2px 8px;'
                    f'border-radius:4px;font-size:0.75em;font-weight:600;">'
                    f'{item["source_name"]}</span>'
                )
                st.markdown(badge_html, unsafe_allow_html=True)
                st.markdown(f"**[{item['title']}]({item['url']})**")

                published = item.get("published_at") or item.get("fetched_at") or ""
                st.caption(f"公開: {published[:16] if published else '不明'}")

                if item.get("summary"):
                    with st.expander("summary を見る"):
                        st.write(item["summary"])

            with col_actions:
                if item.get("prefilter_decision"):
                    label = DECISION_LABELS.get(item["prefilter_decision"], item["prefilter_decision"])
                    st.success(label)
                    if item.get("prefilter_note"):
                        st.caption(f"メモ: {item['prefilter_note']}")
                else:
                    note = st.text_input(
                        "メモ",
                        key=note_key,
                        label_visibility="collapsed",
                        placeholder="メモ (任意)",
                    )
                    bc1, bc2, bc3 = st.columns(3)
                    with bc1:
                        if st.button("採択", key=f"accept_{item_id}", use_container_width=True, type="primary"):
                            update_decision(item_id, "accept", note)
                            st.session_state.page = 0
                            st.rerun()
                    with bc2:
                        if st.button("見送り", key=f"reject_{item_id}", use_container_width=True):
                            update_decision(item_id, "reject", note)
                            st.session_state.page = 0
                            st.rerun()
                    with bc3:
                        if st.button("保留", key=f"defer_{item_id}", use_container_width=True):
                            update_decision(item_id, "defer", note)
                            st.session_state.page = 0
                            st.rerun()

# ── Pagination ────────────────────────────────────────────────────────────────
if total > 0:
    st.divider()
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    p1, p2, p3 = st.columns([1, 2, 1])

    with p1:
        if st.button("← 前へ", disabled=st.session_state.page == 0, use_container_width=True):
            st.session_state.page -= 1
            st.rerun()

    with p2:
        st.markdown(
            f"<div style='text-align:center;padding-top:8px;'>"
            f"{st.session_state.page + 1} / {total_pages} ページ ({total} 件)</div>",
            unsafe_allow_html=True,
        )

    with p3:
        if st.button(
            "次へ →",
            disabled=st.session_state.page >= total_pages - 1,
            use_container_width=True,
        ):
            st.session_state.page += 1
            st.rerun()
