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
- **`translations` table** — Separate storage for multilingual translations (article_id + lang composite PK)
- Supported languages: ja, ko, zh, zh-tw, fr, de, es, pt
- Exponential backoff retry for Gemini 429/RESOURCE_EXHAUSTED errors
- Unit tests for storage and topic loading (9 tests)
