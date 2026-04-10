# icd-collector

[Independent Compute Domain](https://icdomain.github.io/icd-bureau/ja/) の能力評価記事パイプライン。

AI製品・モデルの新リリースを継続的に収集し、DeepMind Cognitive Taxonomyに基づいて人間のどの認知機能に相当するかを分類し、Dreyfusモデル派生の5段階スケールでレベル評価した記事を半自動で生成する。

## 現在のフェーズ

**Phase 0: Collector v0 の実装**

パイプライン全体は4段階 (Collector → Function Mapper → Level Evaluator → Opus Editor) だが、試作期間中はStage 2-4は手動運用とし、Collector v0の実装に集中する。

詳細は [DESIGN.md](./DESIGN.md) を参照。

## Quick start

```bash
# 前提: Python 3.11+
pip install -r requirements.txt

# DBを初期化
python -m collector.init_db

# 収集を1回実行
python -m collector.fetch

# プリフィルタUIを起動
streamlit run ui/prefilter.py
```

## サイトとの関係

このリポジトリは能力評価記事の生成パイプラインのみを扱う。サイト本体 (Jekyllベース) とは別リポジトリ。採択された記事ドラフトはサイトのarchivesディレクトリに手動でコピーして公開する。
