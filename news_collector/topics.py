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
    languages: list[str] = Field(
        default_factory=list,
        description='Target languages for translation (e.g. ["ja", "ko"])',
    )


def load_config(path: str) -> TopicsConfig:
    """Load the full config (topics + languages) from a TOML file.

    Expected format::

        languages = ["ja"]

        [[topics]]
        name = "cybersecurity"
        keywords = ["data breach", "ransomware", "vulnerability"]
    """
    data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    config = TopicsConfig(**data)
    if not config.topics:
        raise ValueError(f"No [[topics]] entries found in {path}")
    return config


def load_topics(path: str) -> list[Topic]:
    """Load topics from a TOML file (convenience wrapper)."""
    return load_config(path).topics


def topic_from_genre(genre: str, keywords: list[str] | None = None) -> Topic:
    """Create a Topic from CLI --genre / --keywords flags (backward compat)."""
    return Topic(name=genre, keywords=keywords or [])
