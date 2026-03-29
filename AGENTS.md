# AGENTS.md — news-collector

News collection, structuring, tagging, and summarization agent.
Collects articles via Gemini + Google Search Grounding, stores in SQLite + JSONL,
tags and summarizes via Gemini Flash.
Part of [cybersecurity-series](https://github.com/nlink-jp/cybersecurity-series).

## Rules

- Project rules: → [CLAUDE.md](CLAUDE.md)
- Organization conventions: → [CONVENTIONS.md](https://github.com/nlink-jp/.github/blob/main/CONVENTIONS.md)

## Build & test

```sh
uv sync           # install dependencies
uv run pytest     # run tests
uv run pyright    # type check
uv tool install . # install as CLI tool
```

## Key structure

```
news_collector/
  cli.py           ← argparse entry point (collect / process subcommands)
  models.py        ← Pydantic Article model (shared schema)
  storage.py       ← SQLite + JSONL dual storage with dedup
  collector.py     ← Gemini 2.5 Pro + Grounding → article discovery
  processor.py     ← Gemini 2.5 Flash → tagging + summarization
tests/
  test_storage.py  ← storage unit tests
```

## Gotchas

- **Two Gemini models**: Collector uses Pro (needs Grounding), Processor uses Flash (low cost). Do not mix them up.
- **Idempotent storage**: `insert()` returns False on duplicate URL hash. `process` skips articles where `processed_at` is not NULL unless `--force` is passed.
- **Date handling**: `--from` / `--to` are inclusive. Default is yesterday for `collect`, no default for `process` (processes all unprocessed).
- **Module path**: `github.com/nlink-jp/news-collector` (Python package: `news_collector`).
- **Env vars**: `GOOGLE_CLOUD_PROJECT` (required), `GOOGLE_CLOUD_LOCATION` (optional, default `us-central1`).
