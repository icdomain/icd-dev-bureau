# DESIGN

## 1. Purpose

本プロジェクトは、Independent Compute Domain サイト上で公開される「AI能力評価記事」の生成を半自動化するパイプラインである。目的は、AI製品・モデルの新リリースに対して以下を継続的に行うこと:

1. 収集: 企業の公式発信と独立評価者の公開レビューを継続監視する
2. 分類: DeepMind Cognitive Taxonomy (Burnell et al., 2026) に基づき、当該技術が主張している認知機能を特定する
3. 評価: 公開ベンチマークと第三者評価に基づき、Dreyfusモデル派生の5段階スケールでレベル判定する
4. 記事化: 中立的で短い記事ドラフトを生成する

本パイプラインは精密な学術評価を目指さない。公開情報に基づく暫定的位置付けとして記事化し、方法論ページで免責する。

## 2. Pipeline overview

```
[Collector] → [Prefilter (manual)] → [Function Mapper] → [Level Evaluator] → [Opus Editor] → [Selector] → [記事ドラフト]
     ↑               ↑                      ↑                    ↑                ↑                ↑
   Phase 0        Phase 0              Phase 1              Phase 1         Phase 1         Phase 2
  (本リポジトリ)    (本リポジトリ)         (手動→後に自動化)    (手動→後に自動化)  (手動→後に自動化) (後に自動化)
```

各Stageの責務:

- **Collector**: RSSとAPIから候補を収集しSQLiteに保存する。重複排除を行う。
- **Prefilter (manual)**: Streamlit UIで候補を人間が目視し、「Function Mapperへ流す / 見送る / 後で見る」を判断する。将来的に自動化する前の判断基準蓄積フェーズを兼ねる。
- **Function Mapper**: 候補テキストを読み、DeepMind Cognitive Taxonomyの10分類に基づいて、主張されている認知機能を抽出する。レベル判定はしない。
- **Level Evaluator**: Function Mapperの出力を受け取り、証拠の種類 (ベンチマークスコア / 独立評価 / デモのみ) に基づいて5段階レベルを付与する。
- **Opus Editor**: Function MapperとLevel Evaluatorの結果を受け取り、サイト文体で記事ドラフトを生成する。評価内容を改変しない編集者として動作する。
- **Selector**: `max(level) ≥ 3` を満たし、かつ過去記事との新規性がある候補のみを記事化キューに載せる。

## 3. Scope

### 3.1 Phase 0 (本リポジトリ初期実装) のスコープ

- Collectorの実装
- Prefilter UIの実装
- SQLiteスキーマの設計と初期化スクリプト
- 14ソースのRSS/API動作確認とリスト固定

### 3.2 Out of scope

以下は将来フェーズで対応する。Phase 0では実装しない。

- **arXiv cs.AI等の論文プレプリント収集**: 流量が大きくシグナル率が低いため、プリフィルタ層を別途設計する必要がある。Phase 0では対象外。将来拡張する場合は別モジュールとして実装する。
- **有料メディア (The Information, Bloomberg, FT等)**: 機械的な継続収集は利用規約上問題がある。これらは人間が週次で読む対象として分離する。
- **Stage 2-4の自動化**: 試作期間中は手動運用 (Claude.ai上でのプロンプト実行) とする。判断基準が明文化されてから自動化する。
- **Selectorの実装**: Stage 2-4が自動化されてから着手する。
- **多言語対応**: Phase 0ではシステム内部は日本語のみ。生成記事は日英バイリンガルだが、これはOpus Editor段階の責務。

## 4. Collector v0 仕様

### 4.1 対象ソース (14件)

#### 企業の公式発信

1. OpenAI Blog (https://openai.com/news/rss.xml)
2. Anthropic News (https://www.anthropic.com/news)
3. Google DeepMind Blog (https://deepmind.google/blog/rss.xml)
4. Meta AI Blog
5. Mistral AI News
6. xAI News

#### 独立評価者 / 分析

7. Simon Willison's Weblog (https://simonwillison.net/atom/everything/)
8. Ethan Mollick "One Useful Thing" (Substack RSS)
9. Nathan Lambert "Interconnects" (Substack RSS)
10. Zvi Mowshowitz "Don't Worry About the Vase" (Substack RSS)

#### プラットフォーム / データベース

11. HuggingFace Trending Models (API)
12. HuggingFace Trending Spaces (API)
13. Papers with Code Trending
14. METR Releases / AI Incident Database

**重要**: 上記のURLの一部は推測を含む。実装開始時に各ソースのRSS/API動作を確認し、動作するエンドポイントに差し替えること。動作しないソースはコメントアウトして残し、後日再確認する。

### 4.2 データスキーマ (SQLite)

```sql
CREATE TABLE sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,        -- "openai_blog" 等の識別子
    display_name TEXT NOT NULL,        -- "OpenAI Blog" 等の表示名
    category TEXT NOT NULL,            -- "vendor" | "independent" | "platform"
    url TEXT NOT NULL,                 -- RSS/API エンドポイント
    fetcher_type TEXT NOT NULL,        -- "rss" | "api_hf" | "api_custom" 等
    active INTEGER NOT NULL DEFAULT 1, -- 無効化フラグ
    last_fetched_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL REFERENCES sources(id),
    external_id TEXT NOT NULL,         -- 元ソースのID/URL (重複排除キー)
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    published_at TIMESTAMP,
    raw_text TEXT,                     -- 本文 (取得できた場合)
    summary TEXT,                      -- RSSのsummary/description
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    prefilter_decision TEXT,           -- NULL | "accept" | "reject" | "defer"
    prefilter_decided_at TIMESTAMP,
    prefilter_note TEXT,               -- 判断理由のメモ (任意)
    UNIQUE(source_id, external_id)
);

CREATE INDEX idx_items_prefilter ON items(prefilter_decision, fetched_at DESC);
CREATE INDEX idx_items_source ON items(source_id, fetched_at DESC);
```

### 4.3 ファイルレイアウト

```
icd-collector/
├── README.md
├── DESIGN.md
├── requirements.txt
├── pyproject.toml
├── collector/
│   ├── __init__.py
│   ├── init_db.py           # DBスキーマ作成とソース初期登録
│   ├── fetch.py             # メインエントリ: 全ソース巡回
│   ├── db.py                # SQLite接続とヘルパ
│   ├── fetchers/
│   │   ├── __init__.py
│   │   ├── base.py          # Fetcher基底クラス
│   │   ├── rss.py           # RSS/Atomフィーチャ
│   │   ├── hf_api.py        # HuggingFace API
│   │   └── custom.py        # 個別対応が必要なソース用
│   └── sources.yaml         # ソース定義 (編集しやすいように別ファイル化)
├── ui/
│   └── prefilter.py         # Streamlit UI
├── tests/
│   ├── test_db.py
│   └── test_fetchers.py
└── data/
    └── .gitkeep             # SQLite DBファイルはgitignore
```

### 4.4 機能要件

#### 4.4.1 `collector/init_db.py`

- `data/collector.db` を作成する (既存の場合は何もしない)
- スキーマを適用する
- `collector/sources.yaml` を読み込んで `sources` テーブルに初期登録する (既存レコードは更新しない)
- 実行: `python -m collector.init_db`

#### 4.4.2 `collector/fetch.py`

- `sources` テーブルから `active = 1` のソースを取得する
- 各ソースに対してfetcher_typeに応じたFetcherを呼び出す
- 取得したアイテムを `items` テーブルに INSERT OR IGNORE する (UNIQUE制約で重複排除)
- 各ソースの `last_fetched_at` を更新する
- 1ソースがエラーになっても他のソースの処理を継続する (エラーはログ出力)
- 実行: `python -m collector.fetch`

#### 4.4.3 `collector/fetchers/rss.py`

- RSS/Atomフィードをfeedparserで取得する
- 各エントリを共通スキーマに変換する: `{external_id, title, url, published_at, summary, raw_text}`
- `external_id` はエントリの `id` または `link` を使う
- User-Agentを明示的に設定する (礼儀として `icd-collector/0.1 (+https://icdomain.github.io/)`)
- タイムアウトは30秒

#### 4.4.4 `collector/fetchers/hf_api.py`

- HuggingFace HubのAPIで trending models / spaces を取得する
- ドキュメント: https://huggingface.co/docs/hub/api
- `external_id` はmodel IDまたはspace IDを使う

#### 4.4.5 `ui/prefilter.py` (Streamlit)

- `prefilter_decision IS NULL` のアイテムを新しい順に表示する
- 各アイテムについて以下を表示:
    - ソース名 (バッジ表示、カテゴリで色分け)
    - タイトル (外部リンク)
    - 公開日時
    - summary (折りたたみ可能)
- 各アイテムに3ボタン: 「採択 (Accept)」「見送り (Reject)」「保留 (Defer)」
- ボタン押下で `prefilter_decision` と `prefilter_decided_at` を更新する
- 「採択理由/却下理由」のオプショナルテキスト入力欄を設ける (`prefilter_note`)
- フィルタ: ソース別、期間別に絞り込めること
- ページネーション: 1画面あたり20件

### 4.5 非機能要件

- エラーハンドリング: 1ソースの失敗が全体を止めないこと
- ログ: 標準出力への構造化ログ (loguru使用を推奨)
- 設定: ソース定義は `sources.yaml` で管理し、コード変更なしで追加・無効化できること
- ネットワーク礼儀: 各ソースへのアクセス間隔は最低1秒空ける
- Rate limit: HuggingFace APIはrate limitがあるので指数バックオフを実装

### 4.6 受け入れ基準

Phase 0完了の条件:

1. `python -m collector.init_db` で DB初期化とソース登録が成功する
2. `python -m collector.fetch` を実行すると、少なくとも8ソース以上から新規アイテムが取得・保存される
3. 同じコマンドを2回実行しても重複レコードが発生しない
4. 1ソースが500エラーを返しても他ソースの処理が継続する
5. `streamlit run ui/prefilter.py` でUIが起動し、取得済みアイテムが表示される
6. UIで3ボタンのいずれかを押すとDBが更新され、該当アイテムが未処理リストから消える
7. `tests/` の基本テストが通る (DB操作、RSS解析の最低限)

## 5. Roadmap

### Phase 0: Collector v0 (本ドキュメントのスコープ)

目標: 14ソースから日次収集し、人力プリフィルタで採択候補を絞り込める状態を作る。

### Phase 1: Stage 2-4 の自動化

- Function Mapper / Level Evaluator / Opus Editor を Anthropic API経由のスクリプト化
- プロンプトファイルを `prompts/` ディレクトリに配置
- Prefilterで採択されたアイテムを自動的にStage 2-4パイプラインに流す
- 生成された記事ドラフトを `drafts/` ディレクトリに出力

### Phase 2: Selector と Novelty Check

- 過去記事インデックスを構築
- `(faculty, domain, level)` タプルでの既出判定
- 優先度付きキューで編集者 (人間) に提示

### Phase 3: 自動プリフィルタ

- Phase 0-1の人力プリフィルタの判断結果を学習データとして蓄積
- Haikuクラスの小型モデルでプリフィルタを自動化
- 人力確認はサンプリングのみに

### Phase 4: arXiv拡張 (要検討)

- arXiv cs.AI を別モジュールとして追加
- 論文専用のプリフィルタ層を設計
- シグナル率が十分高い場合のみ本線に統合

## 6. Technical conventions

- Python 3.11+
- 依存管理: `pyproject.toml` + `requirements.txt` (Claude Code が生成)
- フォーマッタ: `ruff format`
- リンタ: `ruff check`
- 型ヒント: 可能な限り付与、`from __future__ import annotations` を使う
- ログ: loguru
- HTTP: httpx または requests (どちらでも可、Claude Codeの判断)
- 設定: YAMLで `collector/sources.yaml`
- テスト: pytest、最低限のsmokeテストのみでよい
- コミットメッセージ: conventional commits推奨だが強制しない

## 7. References

- Burnell, R. et al. (2026). *Measuring Progress Toward AGI: A Cognitive Framework*. Google DeepMind. https://storage.googleapis.com/deepmind-media/DeepMind.com/Blog/measuring-progress-toward-agi/measuring-progress-toward-agi-a-cognitive-framework.pdf
- Dreyfus, S. E. & Dreyfus, H. L. (1980). *A Five-Stage Model of the Mental Activities Involved in Directed Skill Acquisition*. University of California, Berkeley.
