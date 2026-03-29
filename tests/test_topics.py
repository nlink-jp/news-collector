"""Tests for the topics module."""

import tempfile
from pathlib import Path

import pytest

from news_collector.topics import Topic, load_topics, topic_from_genre


def test_load_topics():
    toml_content = """\
[[topics]]
name = "cybersecurity"
keywords = ["data breach", "ransomware"]

[[topics]]
name = "ai-regulation"
keywords = ["AI regulation", "EU AI Act"]
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(toml_content)
        f.flush()
        topics = load_topics(f.name)

    assert len(topics) == 2
    assert topics[0].name == "cybersecurity"
    assert topics[0].keywords == ["data breach", "ransomware"]
    assert topics[1].name == "ai-regulation"
    assert topics[1].keywords == ["AI regulation", "EU AI Act"]


def test_load_topics_no_keywords():
    toml_content = """\
[[topics]]
name = "general-news"
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(toml_content)
        f.flush()
        topics = load_topics(f.name)

    assert len(topics) == 1
    assert topics[0].name == "general-news"
    assert topics[0].keywords == []


def test_load_topics_empty_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write("")
        f.flush()
        with pytest.raises(ValueError, match="No \\[\\[topics\\]\\]"):
            load_topics(f.name)


def test_topic_from_genre():
    topic = topic_from_genre("cybersecurity", ["ransomware", "phishing"])
    assert topic.name == "cybersecurity"
    assert topic.keywords == ["ransomware", "phishing"]


def test_topic_from_genre_no_keywords():
    topic = topic_from_genre("ai")
    assert topic.name == "ai"
    assert topic.keywords == []
