# news-collector

Gemini + Google Search Grounding でニュース記事を自動収集し、構造化データとして蓄積。タグ付け・要約・多言語翻訳を自動化し、Slack 配信やローカル Web ダッシュボードで閲覧できる CLI ツール。

デイリーバッチで実行し、再利用可能な多言語ニュースアーカイブを構築する。

[English README is here](README.md)

## 特徴

- **マルチトピック収集** — TOML 設定ファイルで複数トピック＋キーワードを定義し、一括バッチ実行
- **ニュースの自動収集** — Gemini 2.5 Pro + Google Search Grounding でジャンル・キーワード・日付範囲を指定して記事を発見・収集
- **構造化ストレージ** — SQLite + JSONL の二重保存、URL ベースの重複排除
- **自動タグ付け** — Gemini 2.5 Flash が記事ごとに 3-8 個のトピックタグを生成
- **自動要約** — Gemini 2.5 Flash が 2-4 文の簡潔な要約を生成
- **多言語翻訳** — タイトルと要約を設定した対象言語（日本語・韓国語・中国語等）に自動翻訳
- **Slack 通知** — 記事を Slack Block Kit JSON（JSONL）で出力。[swrite](https://github.com/nlink-jp/swrite) にパイプして投稿。タグベースの絵文字バッジ付き
- **AI キュレーション** — Gemini Flash がフレンドリーなアナリストコメントを記事ごとに生成して Slack 配信
- **Web ダッシュボード** — FastAPI + Jinja2 のローカル UI。記事一覧（フィルタ/ソート/検索/日付範囲/タグ/言語切替）、記事詳細、ダーク/ライトモード対応
- **投稿追跡** — Slack 投稿済みの記事を記録。notify/curate の再実行で重複投稿しない
- **冪等処理** — タグ付け・要約・翻訳・投稿の各ステップは処理済みをスキップ。再実行しても安全
- **Cloud Run デプロイ** — GCP 上のサーバーレスデイリーバッチ。GCS 永続化対応。[deploy/](deploy/) にセットアップガイド
- **堅牢なリトライ** — 共通の指数バックオフ（6回、最大120秒）で Gemini 429/RESOURCE_EXHAUSTED エラーに対応
- **セキュリティ対策** — SQLi 防止（パラメータバインド）、XSS 防止（tojson フィルタ、safe_url）
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

### 設定ファイル（任意）

`~/.config/news-collector/config.toml` を作成（[config.example.toml](config.example.toml) を参照）:

```toml
project  = "your-project-id"
location = "us-central1"
```

設定の優先順位（高い順）:

1. 環境変数（`NEWS_COLLECTOR_PROJECT`, `NEWS_COLLECTOR_LOCATION`）
2. `GOOGLE_CLOUD_PROJECT` / `GOOGLE_CLOUD_LOCATION` 環境変数（フォールバック）
3. 設定ファイル（`~/.config/news-collector/config.toml`）
4. デフォルト値（location は `us-central1`）

### Google Cloud 認証

```bash
gcloud auth application-default login

# 方法 A: ツール固有の環境変数
export NEWS_COLLECTOR_PROJECT="your-project-id"
export NEWS_COLLECTOR_LOCATION="us-central1"  # 省略可（デフォルト: us-central1）

# 方法 B: 共通環境変数（フォールバック）
export GOOGLE_CLOUD_PROJECT="your-project-id"
export GOOGLE_CLOUD_LOCATION="us-central1"  # 省略可（デフォルト: us-central1）
```

### トピック設定（推奨）

`topics.toml` を作成（[topics.example.toml](topics.example.toml) を参照）:

```toml
languages = ["ja"]

[[topics]]
name = "cybersecurity"
keywords = ["data breach", "ransomware", "vulnerability", "zero-day", "APT"]

[[topics]]
name = "ai-security"
keywords = ["AI security", "LLM vulnerability", "prompt injection"]
```

## 使い方

### 記事の収集

```bash
# topics.toml を使用（バッチ実行に推奨）
news-collector collect --topics topics.toml

# 単一ジャンル＋キーワード指定
news-collector collect --genre cybersecurity --keywords "ransomware,zero-day"

# 日付範囲を指定
news-collector collect --topics topics.toml --from 2026-03-28 --to 2026-03-29

# デフォルト: 昨日のサイバーセキュリティニュースを収集
news-collector collect

# JSONL にも出力
news-collector collect --topics topics.toml --jsonl news.jsonl
```

### 処理（タグ付け + 要約 + 翻訳）

```bash
# topics.toml を使用（languages 設定を読み込む）
news-collector process --topics topics.toml

# または言語を直接指定
news-collector process --languages ja
news-collector process --languages ja,ko,zh

# タグ付け・要約のみ（翻訳なし）
news-collector process

# 特定の日付範囲のみ処理
news-collector process --topics topics.toml --from 2026-03-01 --to 2026-03-31

# 処理済み記事も再処理
news-collector process --force --topics topics.toml
```

### 通知（Slack 出力 — コメントなし）

```bash
# 各記事を Slack Block Kit JSON で出力（1行1記事）
news-collector notify --db news.db --lang ja | while IFS= read -r line; do
  printf '%s' "$line" | swrite post --format blocks --no-unfurl -c "#news"
done

# ジャンル・日付範囲でフィルタ
news-collector notify --db news.db --lang ja --genre cybersecurity --from 2026-03-28
```

### キュレーション（Slack 出力 — AI コメント付き）

```bash
# Gemini Flash がフレンドリーなアナリストコメントを記事ごとに生成
news-collector curate --db news.db --lang ja | while IFS= read -r line; do
  printf '%s' "$line" | swrite post --format blocks --no-unfurl -c "#news"
done
```

### Web UI

```bash
news-collector serve --db news.db --port 8080
# http://127.0.0.1:8080 を開く — ダッシュボード、記事一覧、記事詳細
```

### デイリーバッチの例

```bash
# crontab: 毎日 07:00 に実行
0 7 * * * cd /path/to/data && \
  GOOGLE_CLOUD_PROJECT=your-project-id \
  news-collector collect --topics topics.toml && \
  news-collector process --topics topics.toml
```

### オプション一覧

| コマンド | オプション | デフォルト | 説明 |
|---|---|---|---|
| `collect` | `--topics, -t` | — | トピック・キーワード定義の TOML ファイル |
| `collect` | `--genre, -g` | `cybersecurity` | 単一ジャンル（--topics の代替） |
| `collect` | `--keywords, -k` | — | カンマ区切りキーワード（--genre と併用） |
| `collect` | `--from` | 昨日 | 開始日 (YYYY-MM-DD) |
| `collect` | `--to` | 昨日 | 終了日 (YYYY-MM-DD) |
| `collect` | `--db` | `news.db` | SQLite データベースパス |
| `collect` | `--jsonl` | — | JSONL ファイルにも出力 |
| `process` | `--topics, -t` | — | TOML ファイル（`languages` 設定を読む） |
| `process` | `--languages, -l` | — | 翻訳対象言語（カンマ区切り、例: `ja,ko`） |
| `process` | `--from` | — | 開始日フィルタ |
| `process` | `--to` | — | 終了日フィルタ |
| `process` | `--db` | `news.db` | SQLite データベースパス |
| `process` | `--force` | off | 処理済み記事も再処理 |
| `notify` | `--db` | `news.db` | SQLite データベースパス |
| `notify` | `--lang, -l` | — | この言語の翻訳を使用 |
| `notify` | `--genre, -g` | — | ジャンルでフィルタ |
| `notify` | `--from` / `--to` | — | 日付範囲フィルタ |
| `notify` | `--limit` | `0`（全件） | 最大出力記事数 |
| `curate` | `--db` | `news.db` | SQLite データベースパス |
| `curate` | `--lang, -l` | — | 翻訳・コメントの言語 |
| `curate` | `--genre, -g` | — | ジャンルでフィルタ |
| `curate` | `--from` / `--to` | — | 日付範囲フィルタ |
| `curate` | `--limit` | `0`（全件） | 最大出力記事数 |
| `curate` | `--verbose, -v` | off | stderr に進捗表示 |
| `serve` | `--db` | `news.db` | SQLite データベースパス |
| `serve` | `--host` | `127.0.0.1` | バインドアドレス |
| `serve` | `--port, -p` | `8080` | ポート番号 |
| 共通 | `--verbose, -v` | off | 詳細表示 |

## データスキーマ

### SQLite テーブル: `articles`

| カラム | 型 | 説明 |
|---|---|---|
| `id` | TEXT (PK) | URL ハッシュ（重複排除キー） |
| `title` | TEXT | 記事タイトル（原文） |
| `url` | TEXT | ソース URL |
| `source` | TEXT | メディア名 |
| `published_date` | TEXT | 公開日 (YYYY-MM-DD) |
| `genre` | TEXT | 収集トピック名 |
| `summary_raw` | TEXT | 収集フェーズの生要約 |
| `collected_at` | TEXT | 収集日時 (ISO 8601) |
| `tags` | TEXT | 自動生成タグの JSON 配列 |
| `summary` | TEXT | Gemini Flash 要約（原文） |
| `processed_at` | TEXT | 処理日時 (ISO 8601) |

### SQLite テーブル: `translations`

| カラム | 型 | 説明 |
|---|---|---|
| `article_id` | TEXT (PK) | `articles.id` への外部キー |
| `lang` | TEXT (PK) | 言語コード（例: `ja`, `ko`） |
| `title` | TEXT | 翻訳済みタイトル |
| `summary` | TEXT | 翻訳済み要約 |
| `translated_at` | TEXT | 翻訳日時 (ISO 8601) |

### 対応言語

| コード | 言語 |
|---|---|
| `ja` | 日本語 |
| `ko` | 韓国語 |
| `zh` | 簡体字中国語 |
| `zh-tw` | 繁体字中国語 |
| `fr` | フランス語 |
| `de` | ドイツ語 |
| `es` | スペイン語 |
| `pt` | ポルトガル語 |

## Block Kit デザイン

Slack に投稿される各記事には以下が含まれる:

- タグベースの絵文字バッジ（例: `🚨 [BREACH]`, `⚠️ [CVE]`, `📜 [POLICY]`, `🤖 [AI]`）
- タイトル（リンク付き）＋翻訳タイトル（`--lang` 指定時）
- 要約（翻訳版または原文）
- アナリストコメント（curate のみ、引用ブロック）
- ソースメタデータ、タグ、直リンク URL
- 記事間の divider 区切り

## 開発

```bash
uv sync           # 依存関係のインストール
uv run pytest     # テスト実行
uv run pyright    # 型チェック
```

## 注意事項

- 収集には Gemini 2.5 Pro + Google Search Grounding を使用（Vertex AI 課金あり）
- 処理・翻訳・キュレーションには Gemini 2.5 Flash を使用（低コスト）
- 同じ日付範囲を再収集しても URL ハッシュで重複排除される
- 全処理ステップは冪等: タグ付け・要約・翻訳それぞれ処理済みをスキップ
- リトライ: 共通の指数バックオフ（6回、ベース5秒、最大120秒）＋ジッターで Gemini 429/RESOURCE_EXHAUSTED に対応
- Web UI はパラメータバインド（SQLi 防止）、safe_url/tojson フィルタ（XSS 防止）を使用
