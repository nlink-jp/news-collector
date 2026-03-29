# CLAUDE.md — news-collector

**Organization rules (mandatory): https://github.com/nlink-jp/.github/blob/main/CONVENTIONS.md**

## This project

News collection agent — collects news articles via Gemini + Google Search
Grounding, stores them in SQLite + JSONL, auto-tags, summarizes, and
translates using Gemini Flash, then delivers curated digests to Slack or
a local web dashboard.

Five commands:
- `collect` — discover and store articles (Gemini 2.5 Pro + Grounding)
- `process` — tag, summarize, and translate stored articles (Gemini 2.5 Flash)
- `notify` — output articles as Slack Block Kit JSON (JSONL); pipe to swrite
- `curate` — same as notify but with Gemini Flash analyst commentary per article
- `serve` — FastAPI + Jinja2 local web UI (dashboard, article list, detail)

Multi-topic config via `topics.toml` (topics + keywords + target languages).

## Key structure

```
news_collector/
  cli.py           ← argparse entry point (collect / process / notify / curate / serve)
  models.py        ← Pydantic Article + Translation models
  storage.py       ← SQLite + JSONL dual storage (articles + translations tables)
  collector.py     ← Gemini 2.5 Pro + Grounding → article discovery + URL resolution
  processor.py     ← Gemini 2.5 Flash → tagging + summarization + translation + commentary
  topics.py        ← TOML config loader (topics + keywords + languages)
  retry.py         ← Shared retry logic (6 retries, exponential backoff, max 120s)
  slack.py         ← Slack Block Kit builder (tag→emoji badges, single/digest formats)
  web.py           ← FastAPI + Jinja2 web UI (dashboard, article list, detail, API)
  templates/       ← Jinja2 HTML templates (dashboard, articles, detail)
  static/          ← CSS/JS assets for web UI (dark/light mode)
tests/
  test_storage.py  ← storage unit tests
  test_topics.py   ← topic config loading tests
```

## Build & test

```sh
uv sync           # install dependencies
uv run pytest     # run tests
uv run pyright    # type check
uv tool install . # install as CLI tool
```

## Environment

```sh
export GOOGLE_CLOUD_PROJECT="your-project-id"
export GOOGLE_CLOUD_LOCATION="us-central1"  # optional
gcloud auth application-default login
```

## Design notes

- Storage is idempotent: `insert()` deduplicates by URL hash; tagging, summarization, and translation each skip already-completed work
- Collector uses Gemini 2.5 Pro (needs Grounding for web search); resolves redirect URLs to actual sources
- Processor uses Gemini 2.5 Flash (low cost, sufficient for tagging/summarization/translation/commentary)
- Genre is a parameter, not hardcoded — primary use case is cybersecurity but not limited to it
- Translation uses a separate `translations` table (article_id + lang composite PK) for multi-language support
- notify/curate output JSONL (one JSON line per article); designed to pipe to swrite for individual Slack posts
- curate uses `generate_commentary()` in processor.py for AI analyst comments
- retry.py provides `call_with_retry()` — used by collector and processor for all Gemini API calls
- Web UI uses parameterized SQL (SQLi prevention), safe_url filter and tojson (XSS prevention)
- serve command uses uvicorn to run FastAPI app
