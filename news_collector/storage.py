"""Dual storage backend: SQLite + JSONL."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from news_collector.models import Article

_SCHEMA = """\
CREATE TABLE IF NOT EXISTS articles (
    id             TEXT PRIMARY KEY,
    title          TEXT NOT NULL,
    url            TEXT NOT NULL,
    source         TEXT NOT NULL,
    published_date TEXT,
    genre          TEXT NOT NULL,
    summary_raw    TEXT NOT NULL DEFAULT '',
    collected_at   TEXT NOT NULL,
    tags           TEXT NOT NULL DEFAULT '[]',
    summary        TEXT NOT NULL DEFAULT '',
    processed_at   TEXT
);
"""


class Storage:
    """SQLite + optional JSONL dual storage."""

    def __init__(self, db_path: str, jsonl_path: str | None = None) -> None:
        self._db = sqlite3.connect(db_path)
        self._db.row_factory = sqlite3.Row
        self._db.execute(_SCHEMA)
        self._db.commit()
        self._jsonl_path = jsonl_path

    def close(self) -> None:
        self._db.close()

    def insert(self, article: Article) -> bool:
        """Insert an article. Returns False if the ID already exists (dedup)."""
        try:
            self._db.execute(
                "INSERT INTO articles (id, title, url, source, published_date, genre, summary_raw, collected_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    article.id,
                    article.title,
                    article.url,
                    article.source,
                    article.published_date.isoformat() if article.published_date else None,
                    article.genre,
                    article.summary_raw,
                    article.collected_at.isoformat(),
                ),
            )
            self._db.commit()
        except sqlite3.IntegrityError:
            return False

        if self._jsonl_path:
            with open(self._jsonl_path, "a", encoding="utf-8") as f:
                f.write(article.model_dump_json() + "\n")

        return True

    def get_unprocessed(
        self, from_date: str | None = None, to_date: str | None = None
    ) -> list[Article]:
        """Return articles where processed_at is NULL."""
        query = "SELECT * FROM articles WHERE processed_at IS NULL"
        params: list[str] = []
        if from_date:
            query += " AND collected_at >= ?"
            params.append(from_date)
        if to_date:
            query += " AND collected_at <= ?"
            params.append(to_date + "T23:59:59")
        rows = self._db.execute(query, params).fetchall()
        return [self._row_to_article(r) for r in rows]

    def get_all(
        self, from_date: str | None = None, to_date: str | None = None
    ) -> list[Article]:
        """Return all articles, optionally filtered by date range."""
        query = "SELECT * FROM articles"
        params: list[str] = []
        conditions = []
        if from_date:
            conditions.append("collected_at >= ?")
            params.append(from_date)
        if to_date:
            conditions.append("collected_at <= ?")
            params.append(to_date + "T23:59:59")
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY collected_at DESC"
        rows = self._db.execute(query, params).fetchall()
        return [self._row_to_article(r) for r in rows]

    def update_processed(self, article_id: str, tags: list[str], summary: str, processed_at: str) -> None:
        """Update an article with processing results."""
        self._db.execute(
            "UPDATE articles SET tags = ?, summary = ?, processed_at = ? WHERE id = ?",
            (json.dumps(tags, ensure_ascii=False), summary, processed_at, article_id),
        )
        self._db.commit()

    @staticmethod
    def _row_to_article(row: sqlite3.Row) -> Article:
        d = dict(row)
        d["tags"] = json.loads(d["tags"]) if d["tags"] else []
        return Article(**d)
