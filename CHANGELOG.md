# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-03-29

### Added
- **`collect` command** — Discover and store news articles via Gemini 2.5 Pro + Google Search Grounding
  - Multi-topic support via TOML config file (`--topics`)
  - Per-topic keyword filtering to focus search results
  - Automatic URL resolution (Vertex AI redirect → actual source URL)
  - SQLite + JSONL dual storage with URL-hash deduplication
  - Date range filtering (`--from`, `--to`; default: yesterday)
- **`process` command** — Tag, summarize, and translate collected articles
  - Auto-tagging: 3-8 topic tags per article via Gemini 2.5 Flash
  - Auto-summarization: 2-4 sentence summaries via Gemini 2.5 Flash
  - Multi-language translation: title + summary into configurable languages (`--languages` or `languages` in TOML)
  - Idempotent: each step (tagging, summarization, translation) skips already-completed work
- **`notify` command** — Output articles as Slack Block Kit JSON (JSONL); pipe to swrite for individual posting
  - Tag-based emoji badges per article (BREACH, CVE, POLICY, AI, etc.)
  - Language, genre, date range, and limit filters
- **`curate` command** — Same as notify but with Gemini Flash-generated analyst commentary per article
- **`serve` command** — FastAPI + Jinja2 local web UI
  - Dashboard with article counts, genre breakdown, tag cloud, collection timeline
  - Article list with filtering (genre, tag, search, date range), sorting, pagination, language switching
  - Article detail view with all translations
  - Dark/light mode toggle
- **`translations` table** — Separate storage for multilingual translations (article_id + lang composite PK)
- **Shared retry logic** (`retry.py`) — Exponential backoff (6 retries, base 5s, max 120s) with jitter for Gemini 429/RESOURCE_EXHAUSTED errors
- **Slack Block Kit builder** (`slack.py`) — Tag-to-emoji mapping, single-article and digest message formats
- Supported languages: ja, ko, zh, zh-tw, fr, de, es, pt
- Security: parameterized SQL queries (SQLi prevention), safe_url and tojson filters (XSS prevention)
- Unit tests for storage and topic loading
