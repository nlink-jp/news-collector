"""Tests for the storage module."""

import tempfile
from datetime import date, datetime
from pathlib import Path

from news_collector.models import Article
from news_collector.storage import Storage


def _make_article(url: str = "https://example.com/article-1", **kwargs) -> Article:
    defaults = dict(
        id="abc123",
        title="Test Article",
        url=url,
        source="Example News",
        published_date=date(2026, 3, 29),
        genre="cybersecurity",
        summary_raw="A test article about security.",
        collected_at=datetime(2026, 3, 29, 12, 0, 0),
    )
    defaults.update(kwargs)
    return Article(**defaults)


def test_insert_and_retrieve():
    with tempfile.TemporaryDirectory() as tmp:
        db = str(Path(tmp) / "test.db")
        storage = Storage(db)
        article = _make_article()
        assert storage.insert(article) is True

        articles = storage.get_unprocessed()
        assert len(articles) == 1
        assert articles[0].title == "Test Article"
        storage.close()


def test_insert_dedup():
    with tempfile.TemporaryDirectory() as tmp:
        db = str(Path(tmp) / "test.db")
        storage = Storage(db)
        article = _make_article()
        assert storage.insert(article) is True
        assert storage.insert(article) is False
        storage.close()


def test_update_processed():
    with tempfile.TemporaryDirectory() as tmp:
        db = str(Path(tmp) / "test.db")
        storage = Storage(db)
        article = _make_article()
        storage.insert(article)

        storage.update_processed(
            article.id,
            tags=["ransomware", "healthcare"],
            summary="A security incident in healthcare.",
            processed_at="2026-03-29T13:00:00",
        )

        unprocessed = storage.get_unprocessed()
        assert len(unprocessed) == 0

        all_articles = storage.get_all()
        assert len(all_articles) == 1
        assert all_articles[0].tags == ["ransomware", "healthcare"]
        assert all_articles[0].summary == "A security incident in healthcare."
        storage.close()


def test_jsonl_output():
    with tempfile.TemporaryDirectory() as tmp:
        db = str(Path(tmp) / "test.db")
        jsonl = str(Path(tmp) / "test.jsonl")
        storage = Storage(db, jsonl_path=jsonl)
        storage.insert(_make_article())
        storage.close()

        lines = Path(jsonl).read_text().strip().splitlines()
        assert len(lines) == 1
        assert '"Test Article"' in lines[0]
