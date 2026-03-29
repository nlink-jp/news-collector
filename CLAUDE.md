# CLAUDE.md — news-collector

**Organization rules (mandatory): https://github.com/nlink-jp/.github/blob/main/CONVENTIONS.md**

## This project

News collection agent — collects news articles for a specified genre via
Gemini + Google Search Grounding, stores them in SQLite + JSONL, then
auto-tags and summarizes using Gemini Flash.

Two main commands:
- `collect` — discover and store articles (Gemini 2.5 Pro + Grounding)
- `process` — tag and summarize stored articles (Gemini 2.5 Flash)

## Key structure

```
news_collector/
  cli.py           ← argparse entry point (collect / process subcommands)
  models.py        ← Pydantic Article model
  storage.py       ← SQLite + JSONL dual storage, dedup, idempotent updates
  collector.py     ← Phase 1: Gemini Grounding search → Article list
  processor.py     ← Phase 2: Gemini Flash tagging + summarization
tests/
  test_storage.py  ← storage unit tests
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

- Storage is idempotent: `insert()` deduplicates by URL hash, `process` skips already-processed articles
- Collector uses Gemini 2.5 Pro (needs Grounding for web search)
- Processor uses Gemini 2.5 Flash (low cost, sufficient for tagging/summarization)
- Genre is a parameter, not hardcoded — primary use case is cybersecurity but not limited to it
