# Phase 0 実装レポート

## 作ったもの

DESIGN.md の仕様通り、Collector v0 + Prefilter UI を実装した。

```
collector/init_db.py   DBスキーマ作成・ソース初期登録
collector/fetch.py     全ソース巡回・保存
collector/fetchers/    RSS / HuggingFace API / HF Daily Papers フェッチャー
collector/sources.yaml ソース定義 (14件)
ui/prefilter.py        Streamlit UI (Accept / Reject / Defer)
tests/                 DB操作・RSS解析のsmokeテスト
```

受け入れ基準はすべて達成。10ソースが安定動作中。

---

## 理想通りにできなかったところ ●

### ● 対象14ソースのうち4ソースは取得不可

| ソース | 理由 |
|---|---|
| Meta AI Blog | 公式RSS未提供。RSSHub にも Issue が立っていて未解決。 |
| Mistral AI News | 公式RSS未提供。Next.js SPAのため自動収集不可。 |
| xAI News | 公式RSS未提供。403で完全ブロック。 |
| METR Releases | 公式RSS未提供。ブログはあるが配信形式なし。 |

これらは手動確認対象か、将来 RSSHub 経由での対応を検討する。

### ● Anthropic は公式RSSなし → コミュニティ製フィードで代替

公式 RSS が存在しないため、GitHub Actions で毎時更新されるコミュニティ製フィード (`taobojlen/anthropic-rss-feed`) を使用している。メンテナが止めると止まるリスクあり。

### ● Zvi (Substack) はTLSフィンガープリントでブロック → WordPress ミラーで代替

`thezvi.substack.com/feed` は curl では取得できるが、Python の httpx はTLSフィンガープリントで 403 拒否される。Zvi が WordPress にも同内容をミラーしているため `thezvi.wordpress.com/feed/` で回避した。Substack 側の仕様変更でミラーが止まるリスクあり。

### ● HuggingFace API の `sort=trending` は非対応

DESIGN.md に「HuggingFace Trending Models/Spaces」と書いたが、HF Hub API で `sort=trending` を指定すると 400 エラー。`sort=likes7d`（直近7日のいいね数順）で代替している。厳密な「トレンド」ではない。

### ● Papers with Code は HF に統合済み

`paperswithcode.com/api/v1/` は HuggingFace にリダイレクトされる。`huggingface.co/api/daily_papers` を使用しているが、これは「デイリーペーパー」であり「PWCのトレンド」とは定義が異なる。

---

## 現在の動作ソース (10/14)

| カテゴリ | ソース | 状態 |
|---|---|---|
| vendor | OpenAI Blog | ✅ |
| vendor | Anthropic News | ✅ (コミュニティ製フィード) |
| vendor | Google DeepMind Blog | ✅ |
| vendor | Meta AI Blog | ⛔ RSS未提供 |
| vendor | Mistral AI News | ⛔ RSS未提供 |
| vendor | xAI News | ⛔ RSS未提供 |
| independent | Simon Willison | ✅ |
| independent | Ethan Mollick | ✅ |
| independent | Nathan Lambert | ✅ |
| independent | Zvi Mowshowitz | ✅ (WordPressミラー) |
| platform | HF Trending Models | ✅ (likes7d順) |
| platform | HF Trending Spaces | ✅ (likes7d順) |
| platform | Papers with Code | ✅ (HF Daily Papers) |
| platform | METR Releases | ⛔ RSS未提供 |
