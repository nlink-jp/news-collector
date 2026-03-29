# news-collector

A CLI agent that collects news articles for a specified genre, structures them into a dataset, and automatically tags and summarizes them using Gemini.

Designed for daily batch execution to build a reusable, structured news archive.

[日本語版 README はこちら](README.ja.md)

## Features

- **Automated news collection** — Uses Gemini + Google Search Grounding to discover and collect articles by genre and date range
- **Structured storage** — SQLite database + JSONL export, deduplicated by URL
- **Auto-tagging** — Gemini Flash generates topic tags for each article
- **Auto-summarization** — Gemini Flash produces concise summaries
- **Idempotent processing** — Processor only targets unprocessed articles; safe to re-run
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

```bash
gcloud auth application-default login

export GOOGLE_CLOUD_PROJECT="your-project-id"
export GOOGLE_CLOUD_LOCATION="us-central1"  # optional, defaults to us-central1
```

## Usage

### Collect articles

```bash
# Collect yesterday's cybersecurity news (default)
news-collector collect

# Specify genre and date range
news-collector collect --genre cybersecurity --from 2026-03-28 --to 2026-03-29

# Also output to JSONL
news-collector collect --genre ai --from 2026-03-28 --jsonl news.jsonl

# Verbose mode
news-collector collect -v
```

### Process (tag + summarize)

```bash
# Process all unprocessed articles
news-collector process

# Process a specific date range
news-collector process --from 2026-03-01 --to 2026-03-31

# Force re-process already processed articles
news-collector process --force
```

### Options

| Command | Option | Default | Description |
|---|---|---|---|
| `collect` | `--genre, -g` | `cybersecurity` | News genre to collect |
| `collect` | `--from` | yesterday | Start date (YYYY-MM-DD) |
| `collect` | `--to` | yesterday | End date (YYYY-MM-DD) |
| `collect` | `--db` | `news.db` | SQLite database path |
| `collect` | `--jsonl` | — | Also append to JSONL file |
| `process` | `--from` | — | Start date filter |
| `process` | `--to` | — | End date filter |
| `process` | `--db` | `news.db` | SQLite database path |
| `process` | `--force` | off | Re-process already processed articles |
| both | `--verbose, -v` | off | Show detailed progress |

### Daily batch example

```bash
# crontab: run at 07:00 every day
0 7 * * * cd /path/to/data && news-collector collect && news-collector process
```

## Data Schema

### SQLite table: `articles`

| Column | Type | Description |
|---|---|---|
| `id` | TEXT (PK) | URL hash (dedup key) |
| `title` | TEXT | Article title |
| `url` | TEXT | Source URL |
| `source` | TEXT | Media/publisher name |
| `published_date` | TEXT | Publication date (YYYY-MM-DD) |
| `genre` | TEXT | Collection genre |
| `summary_raw` | TEXT | Raw summary from collection phase |
| `collected_at` | TEXT | Collection timestamp (ISO 8601) |
| `tags` | TEXT | JSON array of auto-generated tags |
| `summary` | TEXT | Gemini Flash summary |
| `processed_at` | TEXT | Processing timestamp (ISO 8601) |

### JSONL format

Each line is a JSON object matching the `Article` Pydantic model.

## Building

```bash
# Run tests
uv run pytest

# Type checking
uv run pyright
```

## Notes

- Collection uses Gemini 2.5 Pro with Google Search Grounding (Vertex AI costs apply)
- Processing uses Gemini 2.5 Flash for low-cost tagging and summarization
- Articles are deduplicated by URL hash; re-collecting the same date range is safe
