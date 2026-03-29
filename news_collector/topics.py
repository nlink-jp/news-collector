"""Topic configuration loader."""

from __future__ import annotations

import sys
from pathlib import Path

from pydantic import BaseModel, Field

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        import tomli as tomllib  # type: ignore[no-redef]


class Topic(BaseModel):
    """A single topic to collect news about."""

    name: str = Field(description="Topic label (used as genre in storage)")
    keywords: list[str] = Field(
        default_factory=list,
        description="Search keywords to focus the collection",
    )


class TopicsConfig(BaseModel):
    """Top-level topics configuration."""

    topics: list[Topic] = Field(default_factory=list)


def load_topics(path: str) -> list[Topic]:
    """Load topics from a TOML file.

    Expected format::

        [[topics]]
        name = "cybersecurity"
        keywords = ["data breach", "ransomware", "vulnerability"]

        [[topics]]
        name = "ai-regulation"
        keywords = ["AI regulation", "AI safety", "EU AI Act"]
    """
    data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    config = TopicsConfig(**data)
    if not config.topics:
        raise ValueError(f"No [[topics]] entries found in {path}")
    return config.topics


def topic_from_genre(genre: str, keywords: list[str] | None = None) -> Topic:
    """Create a Topic from CLI --genre / --keywords flags (backward compat)."""
    return Topic(name=genre, keywords=keywords or [])
