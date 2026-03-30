# AGENTS.md — news-collector

News collection, structuring, tagging, summarization, translation, and delivery agent.
Collects articles via Gemini + Google Search Grounding, stores in SQLite + JSONL,
tags and summarizes via Gemini Flash, translates into configurable languages,
and delivers curated digests to Slack (via swrite) or a local web dashboard.
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

## Gotchas

- **Two Gemini models**: Collector uses Pro (needs Grounding), Processor uses Flash (low cost). Do not mix them up.
- **Three idempotent steps**: tagging (`processed_at`), summarization (same), and translation (`translations` table PK). Each skips already-completed work.
- **URL resolution**: Grounding returns redirect URLs (`vertexaisearch.cloud.google.com`); collector resolves them to actual source URLs via HTTP HEAD.
- **Multi-topic config**: `topics.toml` defines topics + keywords + languages. Both `collect` and `process` accept `--topics`.
- **Notification tracking**: notify/curate mark articles as `notified_at` after output. Re-running only posts new articles.
- **TZ required in Cloud Run**: container defaults to UTC. Set `TZ=Asia/Tokyo` to get correct "yesterday" in JST.
- **Date handling**: `--from` / `--to` are inclusive. Default is yesterday for `collect`, no default for `process` (processes all unprocessed).
- **Module path**: `github.com/nlink-jp/news-collector` (Python package: `news_collector`).
- **Env vars**: `GOOGLE_CLOUD_PROJECT` (required), `GOOGLE_CLOUD_LOCATION` (optional, default `us-central1`).
- **notify/curate output**: JSONL format (one JSON line per article). Designed to pipe each line individually to `swrite post --format blocks --no-unfurl`.
- **curate vs notify**: curate calls `generate_commentary()` in processor.py which requires a Gemini client; notify is offline (no API calls).
- **retry.py**: All Gemini API calls should use `call_with_retry()`. 6 retries, exponential backoff (5s base), capped at 120s, with ±1s jitter.
- **slack.py tag badges**: `_TAG_BADGE` dict maps tag names to emoji+label pairs. Unrecognized tags fall back to the default NEWS badge.
- **Web UI security**: storage.py uses parameterized queries (never string interpolation). Templates use `tojson` for JSON embedding and `safe_url` filter to prevent javascript: URLs.
- **serve command**: Runs uvicorn directly; no ASGI middleware. For production, use a reverse proxy.
