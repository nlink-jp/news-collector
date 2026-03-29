# CLAUDE.md — news-collector

**Organization rules (mandatory): https://github.com/nlink-jp/.github/blob/main/CONVENTIONS.md**

## This project

News collection agent — collects news articles via Gemini + Google Search
Grounding, stores them in SQLite + JSONL, then auto-tags, summarizes, and
translates using Gemini Flash.

Two main commands:
- `collect` — discover and store articles (Gemini 2.5 Pro + Grounding)
- `process` — tag, summarize, and translate stored articles (Gemini 2.5 Flash)

Multi-topic config via `topics.toml` (topics + keywords + target languages).

## Key structure

```
news_collector/
  cli.py           ← argparse entry point (collect / process subcommands)
  models.py        ← Pydantic Article + Translation models
  storage.py       ← SQLite + JSONL dual storage (articles + translations tables)
  collector.py     ← Gemini 2.5 Pro + Grounding → article discovery + URL resolution
  processor.py     ← Gemini 2.5 Flash → tagging + summarization + translation
  topics.py        ← TOML config loader (topics + keywords + languages)
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
- Processor uses Gemini 2.5 Flash (low cost, sufficient for tagging/summarization/translation)
- Genre is a parameter, not hardcoded — primary use case is cybersecurity but not limited to it
- Translation uses a separate `translations` table (article_id + lang composite PK) for multi-language support
