"""Phase 2: Tag and summarize collected articles via Gemini Flash."""

from __future__ import annotations

import argparse
import json
import os
import sys

from datetime import datetime

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from news_collector.models import Translation
from news_collector.retry import call_with_retry
from news_collector.storage import Storage
from news_collector.topics import load_config

_FLASH_MODEL = "gemini-2.5-flash"

# ──────────────────────────────────────────────
# Response model
# ──────────────────────────────────────────────

class _ProcessingResult(BaseModel):
    """Structured output from the tagging and summarization step."""

    tags: list[str] = Field(
        description="Topic tags for the article (3-8 tags). "
        "Use lowercase, specific terms. Examples: ransomware, data-breach, "
        "healthcare, cve, phishing, zero-day, nation-state, policy"
    )
    summary: str = Field(
        description="Concise summary of the article in 2-4 sentences. "
        "Include: what happened, who was affected, and why it matters."
    )

# ──────────────────────────────────────────────
# Prompt
# ──────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a cybersecurity news analyst. Given a news article's title and raw
summary, produce:

1. **Tags**: 3-8 lowercase topic tags that categorize the article.
   Use specific, reusable terms such as:
   - Incident type: data-breach, ransomware, phishing, zero-day, supply-chain, ddos
   - Sector: healthcare, finance, government, education, retail, critical-infrastructure
   - Actor: nation-state, apt, hacktivist, insider-threat
   - Topic: vulnerability, cve, policy, regulation, ai-security, cloud-security
   - Region: us, eu, asia, middle-east (only if geographically significant)

2. **Summary**: A concise 2-4 sentence summary covering what happened,
   who was affected, and the significance.

Be factual. Do not speculate beyond what the input states.
"""

# ──────────────────────────────────────────────
# Client factory
# ──────────────────────────────────────────────

def _make_client() -> genai.Client:
    return genai.Client(
        vertexai=True,
        project=os.environ["GOOGLE_CLOUD_PROJECT"],
        location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
    )

# ──────────────────────────────────────────────
# Core processing
# ──────────────────────────────────────────────

def generate_tags_and_summary(
    client: genai.Client, title: str, raw_summary: str
) -> tuple[list[str], str]:
    """Generate tags and summary for a single article using Gemini Flash."""

    def _run() -> tuple[list[str], str]:
        response = client.models.generate_content(
            model=_FLASH_MODEL,
            contents=(
                f"Article title: {title}\n\n"
                f"Raw summary:\n{raw_summary}"
            ),
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=_ProcessingResult,
            ),
        )
        data = json.loads(response.text)
        result = _ProcessingResult(**data)
        return result.tags, result.summary

    return call_with_retry(_run, "process")

# ──────────────────────────────────────────────
# Translation
# ──────────────────────────────────────────────

_LANG_NAMES: dict[str, str] = {
    "ja": "Japanese",
    "ko": "Korean",
    "zh": "Simplified Chinese",
    "zh-tw": "Traditional Chinese",
    "fr": "French",
    "de": "German",
    "es": "Spanish",
    "pt": "Portuguese",
}

class _TranslationResult(BaseModel):
    """Structured output from the translation step."""

    title: str = Field(description="Translated article title")
    summary: str = Field(description="Translated article summary")

def translate_article(
    client: genai.Client, title: str, summary: str, lang: str
) -> tuple[str, str]:
    """Translate title and summary into the target language using Gemini Flash."""
    lang_name = _LANG_NAMES.get(lang, lang)

    def _run() -> tuple[str, str]:
        response = client.models.generate_content(
            model=_FLASH_MODEL,
            contents=(
                f"Translate the following news article title and summary into {lang_name}.\n\n"
                f"Title: {title}\n\n"
                f"Summary:\n{summary}"
            ),
            config=types.GenerateContentConfig(
                system_instruction=(
                    f"You are a professional translator. Translate the given text into "
                    f"{lang_name} accurately and naturally. Preserve technical terms "
                    f"(CVE IDs, product names, organization names) as-is. "
                    f"Do not add or omit information."
                ),
                response_mime_type="application/json",
                response_schema=_TranslationResult,
            ),
        )
        data = json.loads(response.text)
        result = _TranslationResult(**data)
        return result.title, result.summary

    return call_with_retry(_run, f"translate-{lang}")

# ──────────────────────────────────────────────
# Curation (analyst commentary)
# ──────────────────────────────────────────────

class _CurationResult(BaseModel):
    """Structured output from the curation step."""

    commentary: str = Field(
        description="A concise analyst commentary on the article (2-3 sentences). "
        "Provide context, significance, and actionable insight."
    )

def generate_commentary(
    client: genai.Client, title: str, summary: str, tags: list[str], lang: str = ""
) -> str:
    """Generate an analyst commentary for a single article using Gemini Flash."""
    lang_name = _LANG_NAMES.get(lang, "English") if lang else "English"
    tag_str = ", ".join(tags) if tags else "general"

    def _run() -> str:
        response = client.models.generate_content(
            model=_FLASH_MODEL,
            contents=(
                f"Article title: {title}\n"
                f"Summary: {summary}\n"
                f"Tags: {tag_str}"
            ),
            config=types.GenerateContentConfig(
                system_instruction=(
                    f"You are an experienced cybersecurity analyst providing "
                    f"brief commentary on news articles for a security team's Slack channel. "
                    f"Write in {lang_name}.\n\n"
                    f"For each article, provide a 2-3 sentence commentary that:\n"
                    f"- Explains why this matters to security practitioners\n"
                    f"- Adds context that isn't obvious from the headline\n"
                    f"- Suggests a concrete action or takeaway when appropriate\n\n"
                    f"Be direct, professional, and insightful. No filler."
                ),
                response_mime_type="application/json",
                response_schema=_CurationResult,
            ),
        )
        data = json.loads(response.text)
        result = _CurationResult(**data)
        return result.commentary

    return call_with_retry(_run, "curate")

# ──────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────

def run_process(args: argparse.Namespace) -> None:
    """Entry point for the process subcommand."""
    client = _make_client()
    storage = Storage(args.db)

    # Resolve target languages from --topics file or --languages flag
    languages: list[str] = []
    if args.topics:
        config = load_config(args.topics)
        languages = config.languages
    if args.languages:
        languages = [l.strip() for l in args.languages.split(",")]

    try:
        # Phase 1: Tag and summarize
        if args.force:
            articles = storage.get_all(args.from_date, args.to_date)
        else:
            articles = storage.get_unprocessed(args.from_date, args.to_date)

        if articles:
            print(f"Tagging and summarizing {len(articles)} articles...", file=sys.stderr)
            processed = 0
            for article in articles:
                tags, summary = generate_tags_and_summary(
                    client, article.title, article.summary_raw
                )
                storage.update_processed(
                    article.id,
                    tags=tags,
                    summary=summary,
                    processed_at=datetime.now().isoformat(),
                )
                processed += 1
                if args.verbose:
                    print(f"  ✓ [{processed}/{len(articles)}] {article.title}", file=sys.stderr)
                    print(f"    tags: {tags}", file=sys.stderr)
                else:
                    print(f"  ✓ {processed}/{len(articles)}", end="\r", file=sys.stderr)
            print(f"\nDone: {processed} articles tagged.", file=sys.stderr)
        else:
            print("No articles to tag.", file=sys.stderr)

        # Phase 2: Translate
        if not languages:
            return

        for lang in languages:
            untranslated = storage.get_untranslated(lang, args.from_date, args.to_date)
            if not untranslated:
                print(f"No articles to translate to {lang}.", file=sys.stderr)
                continue

            print(f"\nTranslating {len(untranslated)} articles to {lang}...", file=sys.stderr)
            translated = 0
            for article in untranslated:
                # Use processed summary if available, otherwise raw
                source_summary = article.summary or article.summary_raw
                t_title, t_summary = translate_article(
                    client, article.title, source_summary, lang
                )
                storage.upsert_translation(Translation(
                    article_id=article.id,
                    lang=lang,
                    title=t_title,
                    summary=t_summary,
                    translated_at=datetime.now(),
                ))
                translated += 1
                if args.verbose:
                    print(f"  ✓ [{translated}/{len(untranslated)}] {t_title}", file=sys.stderr)
                else:
                    print(f"  ✓ {translated}/{len(untranslated)}", end="\r", file=sys.stderr)
            print(f"\nDone: {translated} articles translated to {lang}.", file=sys.stderr)
    finally:
        storage.close()
