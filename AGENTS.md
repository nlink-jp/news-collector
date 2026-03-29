# AGENTS.md — news-collector

News collection, structuring, tagging, summarization, and translation agent.
Collects articles via Gemini + Google Search Grounding, stores in SQLite + JSONL,
tags and summarizes via Gemini Flash, and translates into configurable languages.
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
  models.py        ← Pydantic Article + Translation models
  storage.py       ← SQLite + JSONL dual storage (articles + translations tables)
  collector.py     ← Gemini 2.5 Pro + Grounding → article discovery + URL resolution
  processor.py     ← Gemini 2.5 Flash → tagging + summarization + translation
  topics.py        ← TOML config loader (topics + keywords + languages)
tests/
  test_storage.py  ← storage unit tests
  test_topics.py   ← topic config loading tests
```

## Gotchas

- **Two Gemini models**: Collector uses Pro (needs Grounding), Processor uses Flash (low cost). Do not mix them up.
- **Three idempotent steps**: tagging (`processed_at`), summarization (same), and translation (`translations` table PK). Each skips already-completed work.
- **URL resolution**: Grounding returns redirect URLs (`vertexaisearch.cloud.google.com`); collector resolves them to actual source URLs via HTTP HEAD.
- **Multi-topic config**: `topics.toml` defines topics + keywords + languages. Both `collect` and `process` accept `--topics`.
- **Date handling**: `--from` / `--to` are inclusive. Default is yesterday for `collect`, no default for `process` (processes all unprocessed).
- **Module path**: `github.com/nlink-jp/news-collector` (Python package: `news_collector`).
- **Env vars**: `GOOGLE_CLOUD_PROJECT` (required), `GOOGLE_CLOUD_LOCATION` (optional, default `us-central1`).
