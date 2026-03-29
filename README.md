# news-collector

A CLI agent that collects news articles via Gemini + Google Search Grounding, structures them into a dataset, and automatically tags, summarizes, and translates them.

Designed for daily batch execution to build a reusable, structured, multilingual news archive.

[日本語版 README はこちら](README.ja.md)

## Features

- **Multi-topic collection** — Define multiple topics with keywords in a TOML config file; each topic is collected independently in a single batch run
- **Automated news collection** — Uses Gemini 2.5 Pro + Google Search Grounding to discover and collect articles by genre, keywords, and date range
- **Structured storage** — SQLite database + optional JSONL export, deduplicated by URL
- **Auto-tagging** — Gemini 2.5 Flash generates 3-8 topic tags per article
- **Auto-summarization** — Gemini 2.5 Flash produces concise 2-4 sentence summaries
- **Multi-language translation** — Translates titles and summaries into configurable target languages (Japanese, Korean, Chinese, etc.) via Gemini Flash
- **Idempotent processing** — All steps (tagging, summarization, translation) skip already-completed work; safe to re-run
- **Batch-friendly** — Designed for cron/launchd daily execution

## Installation

**Prerequisites:** Python 3.11+, [uv](https://docs.astral.sh/uv/), and a Google Cloud project with Vertex AI API enabled.

```bash
uv tool install git+https://github.com/nlink-jp/news-collector.git
```

Or clone and install locally:

```bash
git clone https://github.com/nlink-jp/news-collector.git
cd news-collector
uv tool install .
```

## Configuration

### Google Cloud authentication

```bash
gcloud auth application-default login

export GOOGLE_CLOUD_PROJECT="your-project-id"
export GOOGLE_CLOUD_LOCATION="us-central1"  # optional, defaults to us-central1
```

### Topic configuration (recommended)

Create a `topics.toml` file (see [topics.example.toml](topics.example.toml)):

```toml
languages = ["ja"]

[[topics]]
name = "cybersecurity"
keywords = ["data breach", "ransomware", "vulnerability", "zero-day", "APT"]

[[topics]]
name = "ai-security"
keywords = ["AI security", "LLM vulnerability", "prompt injection"]
```

## Usage

### Collect articles

```bash
# Using topics.toml (recommended for batch)
news-collector collect --topics topics.toml

# Single genre with keywords
news-collector collect --genre cybersecurity --keywords "ransomware,zero-day"

# Specify date range
news-collector collect --topics topics.toml --from 2026-03-28 --to 2026-03-29

# Default: collect yesterday's cybersecurity news
news-collector collect

# Also output to JSONL
news-collector collect --topics topics.toml --jsonl news.jsonl
```

### Process (tag + summarize + translate)

```bash
# Using topics.toml (reads languages config)
news-collector process --topics topics.toml

# Or specify languages directly
news-collector process --languages ja
news-collector process --languages ja,ko,zh

# Tag and summarize only (no translation)
news-collector process

# Process a specific date range
news-collector process --topics topics.toml --from 2026-03-01 --to 2026-03-31

# Force re-process already processed articles
news-collector process --force --topics topics.toml
```

### Daily batch example

```bash
# crontab: run at 07:00 every day
0 7 * * * cd /path/to/data && \
  GOOGLE_CLOUD_PROJECT=your-project-id \
  news-collector collect --topics topics.toml && \
  news-collector process --topics topics.toml
```

### Options

| Command | Option | Default | Description |
|---|---|---|---|
| `collect` | `--topics, -t` | — | TOML file defining topics and keywords |
| `collect` | `--genre, -g` | `cybersecurity` | Single genre (alternative to --topics) |
| `collect` | `--keywords, -k` | — | Comma-separated keywords (with --genre) |
| `collect` | `--from` | yesterday | Start date (YYYY-MM-DD) |
| `collect` | `--to` | yesterday | End date (YYYY-MM-DD) |
| `collect` | `--db` | `news.db` | SQLite database path |
| `collect` | `--jsonl` | — | Also append to JSONL file |
| `process` | `--topics, -t` | — | TOML file (reads `languages` field) |
| `process` | `--languages, -l` | — | Comma-separated target languages (e.g. `ja,ko`) |
| `process` | `--from` | — | Start date filter |
| `process` | `--to` | — | End date filter |
| `process` | `--db` | `news.db` | SQLite database path |
| `process` | `--force` | off | Re-process already processed articles |
| both | `--verbose, -v` | off | Show detailed progress |

## Data Schema

### SQLite table: `articles`

| Column | Type | Description |
|---|---|---|
| `id` | TEXT (PK) | URL hash (dedup key) |
| `title` | TEXT | Article title (original language) |
| `url` | TEXT | Source URL |
| `source` | TEXT | Media/publisher name |
| `published_date` | TEXT | Publication date (YYYY-MM-DD) |
| `genre` | TEXT | Collection genre/topic name |
| `summary_raw` | TEXT | Raw summary from collection phase |
| `collected_at` | TEXT | Collection timestamp (ISO 8601) |
| `tags` | TEXT | JSON array of auto-generated tags |
| `summary` | TEXT | Gemini Flash summary (original language) |
| `processed_at` | TEXT | Processing timestamp (ISO 8601) |

### SQLite table: `translations`

| Column | Type | Description |
|---|---|---|
| `article_id` | TEXT (PK) | References `articles.id` |
| `lang` | TEXT (PK) | Language code (e.g. `ja`, `ko`) |
| `title` | TEXT | Translated title |
| `summary` | TEXT | Translated summary |
| `translated_at` | TEXT | Translation timestamp (ISO 8601) |

### Supported languages

| Code | Language |
|---|---|
| `ja` | Japanese |
| `ko` | Korean |
| `zh` | Simplified Chinese |
| `zh-tw` | Traditional Chinese |
| `fr` | French |
| `de` | German |
| `es` | Spanish |
| `pt` | Portuguese |

### JSONL format

Each line is a JSON object matching the `Article` Pydantic model.

## Building

```bash
uv sync           # install dependencies
uv run pytest     # run tests (9 tests)
uv run pyright    # type checking
```

## Notes

- Collection uses Gemini 2.5 Pro with Google Search Grounding (Vertex AI costs apply)
- Processing and translation use Gemini 2.5 Flash (low cost)
- Articles are deduplicated by URL hash; re-collecting the same date range is safe
- All processing steps are idempotent: tagging, summarization, and translation each skip already-completed work
