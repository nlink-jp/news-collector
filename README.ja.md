# news-collector

指定ジャンルのニュース記事を自動収集し、構造化データとして蓄積。Gemini によるタグ付け・要約の自動化まで行う CLI ツール。

デイリーバッチで実行し、再利用可能なニュースアーカイブを構築する。

[English README is here](README.md)

## 特徴

- **ニュースの自動収集** — Gemini + Google Search Grounding でジャンル・日付範囲を指定して記事を発見・収集
- **構造化ストレージ** — SQLite + JSONL の二重保存、URL ベースの重複排除
- **自動タグ付け** — Gemini Flash がトピックタグを生成
- **自動要約** — Gemini Flash が簡潔な要約を生成
- **冪等処理** — Processor は未処理記事のみを対象。再実行しても安全
- **バッチ実行対応** — cron / launchd でのデイリー実行を想定

## インストール

**前提条件:** Python 3.11+、[uv](https://docs.astral.sh/uv/)、Google Cloud プロジェクト（Vertex AI API 有効化済み）

```bash
uv tool install git+https://github.com/nlink-jp/news-collector.git
```

またはローカルにクローン:

```bash
git clone https://github.com/nlink-jp/news-collector.git
cd news-collector
uv tool install .
```

## 設定

```bash
gcloud auth application-default login

export GOOGLE_CLOUD_PROJECT="your-project-id"
export GOOGLE_CLOUD_LOCATION="us-central1"  # 省略可（デフォルト: us-central1）
```

## 使い方

### 記事の収集

```bash
# 昨日のサイバーセキュリティニュースを収集（デフォルト）
news-collector collect

# ジャンルと日付範囲を指定
news-collector collect --genre cybersecurity --from 2026-03-28 --to 2026-03-29

# JSONL にも出力
news-collector collect --genre ai --from 2026-03-28 --jsonl news.jsonl

# 詳細表示
news-collector collect -v
```

### 処理（タグ付け + 要約）

```bash
# 未処理の全記事を処理
news-collector process

# 特定の日付範囲のみ処理
news-collector process --from 2026-03-01 --to 2026-03-31

# 処理済み記事も再処理
news-collector process --force
```

### デイリーバッチの例

```bash
# crontab: 毎日 07:00 に実行
0 7 * * * cd /path/to/data && news-collector collect && news-collector process
```

## データスキーマ

### SQLite テーブル: `articles`

| カラム | 型 | 説明 |
|---|---|---|
| `id` | TEXT (PK) | URL ハッシュ（重複排除キー） |
| `title` | TEXT | 記事タイトル |
| `url` | TEXT | ソース URL |
| `source` | TEXT | メディア名 |
| `published_date` | TEXT | 公開日 (YYYY-MM-DD) |
| `genre` | TEXT | 収集ジャンル |
| `summary_raw` | TEXT | 収集フェーズの生要約 |
| `collected_at` | TEXT | 収集日時 (ISO 8601) |
| `tags` | TEXT | 自動生成タグの JSON 配列 |
| `summary` | TEXT | Gemini Flash 要約 |
| `processed_at` | TEXT | 処理日時 (ISO 8601) |

## 開発

```bash
# テスト実行
uv run pytest

# 型チェック
uv run pyright
```

## 注意事項

- 収集には Gemini 2.5 Pro + Google Search Grounding を使用（Vertex AI 課金あり）
- 処理には Gemini 2.5 Flash を使用（低コスト）
- 同じ日付範囲を再収集しても URL ハッシュで重複排除される
