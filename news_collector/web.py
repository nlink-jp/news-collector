"""Web UI for browsing collected news articles."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from news_collector.storage import Storage

_HERE = Path(__file__).parent
_TEMPLATES = Jinja2Templates(directory=str(_HERE / "templates"))
_TEMPLATES.env.filters["safe_url"] = lambda u: u if u and u.lower().startswith(("http://", "https://")) else ""
_SAFE_SCHEMES = ("http://", "https://")


def _safe_url(url: str) -> str:
    """Sanitize a URL: only allow http/https schemes to prevent javascript: XSS."""
    if url and url.lower().startswith(_SAFE_SCHEMES):
        return url
    return ""


def create_app(db_path: str) -> FastAPI:
    """Create the FastAPI application."""
    app = FastAPI(title="news-collector", docs_url=None, redoc_url=None)
    app.mount("/static", StaticFiles(directory=str(_HERE / "static")), name="static")

    def _storage() -> Storage:
        return Storage(db_path)

    # ── Dashboard ──

    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request):
        storage = _storage()
        try:
            articles = storage.get_all()
            genres: dict[str, int] = {}
            tags_count: dict[str, int] = {}
            dates: dict[str, int] = {}
            for a in articles:
                genres[a.genre] = genres.get(a.genre, 0) + 1
                for tag in a.tags:
                    tags_count[tag] = tags_count.get(tag, 0) + 1
                day = a.collected_at.strftime("%Y-%m-%d")
                dates[day] = dates.get(day, 0) + 1

            top_tags = sorted(tags_count.items(), key=lambda x: -x[1])[:30]
            sorted_dates = sorted(dates.items())

            notified_count = sum(1 for a in articles if a.notified_at)

            return _TEMPLATES.TemplateResponse(request, "dashboard.html", {
                "total": len(articles),
                "notified": notified_count,
                "tagged": sum(1 for a in articles if a.processed_at),
                "genres": sorted(genres.items(), key=lambda x: -x[1]),
                "top_tags": top_tags,
                "dates": sorted_dates,
                "dates_json": json.dumps(sorted_dates),
            })
        finally:
            storage.close()

    # ── Article list ──

    @app.get("/articles", response_class=HTMLResponse)
    def article_list(
        request: Request,
        genre: str = "",
        tag: str = "",
        q: str = "",
        lang: str = "",
        page: int = Query(1, ge=1),
        from_date: str = Query("", alias="from"),
        to_date: str = Query("", alias="to"),
        sort: str = Query("desc"),
        notified: str = Query(""),
    ):
        storage = _storage()
        try:
            articles = storage.get_all(from_date=from_date or None, to_date=to_date or None)
            # Sort by collected_at
            if sort == "asc":
                articles.sort(key=lambda a: a.collected_at)
            else:
                articles.sort(key=lambda a: a.collected_at, reverse=True)
            # Notification filter
            if notified == "yes":
                articles = [a for a in articles if a.notified_at]
            elif notified == "no":
                articles = [a for a in articles if not a.notified_at]

            if genre:
                articles = [a for a in articles if a.genre == genre]
            if tag:
                articles = [a for a in articles if tag in a.tags]
            if q:
                q_lower = q.lower()
                articles = [
                    a for a in articles
                    if q_lower in a.title.lower() or q_lower in a.summary.lower()
                    or q_lower in a.summary_raw.lower()
                ]

            # Load translations if language selected
            if lang:
                for a in articles:
                    a.translations = storage.get_translations(a.id)

            # Pagination
            per_page = 20
            total_pages = max(1, (len(articles) + per_page - 1) // per_page)
            page = min(page, total_pages)
            start = (page - 1) * per_page
            page_articles = articles[start:start + per_page]

            # Collect available genres, tags, and languages for filters
            all_articles = storage.get_all()
            all_genres = sorted(set(a.genre for a in all_articles))
            all_langs = _get_available_languages(storage)
            tags_count: dict[str, int] = {}
            for a in all_articles:
                for t in a.tags:
                    tags_count[t] = tags_count.get(t, 0) + 1
            all_tags = sorted(tags_count.items(), key=lambda x: -x[1])[:50]

            return _TEMPLATES.TemplateResponse(request, "articles.html", {
                "articles": page_articles,
                "total": len(articles),
                "page": page,
                "total_pages": total_pages,
                "genre": genre,
                "tag": tag,
                "q": q,
                "lang": lang,
                "sort": sort,
                "from_date": from_date,
                "to_date": to_date,
                "notified": notified,
                "all_genres": all_genres,
                "all_langs": all_langs,
                "all_tags": all_tags,
            })
        finally:
            storage.close()

    # ── Article detail ──

    @app.get("/articles/{article_id}", response_class=HTMLResponse)
    def article_detail(request: Request, article_id: str):
        storage = _storage()
        try:
            articles = storage.get_all()
            article = next((a for a in articles if a.id == article_id), None)
            if article is None:
                return HTMLResponse("Article not found", status_code=404)

            article.translations = storage.get_translations(article_id)

            return _TEMPLATES.TemplateResponse(request, "detail.html", {
                "article": article,
            })
        finally:
            storage.close()

    # ── API (JSON) ──

    @app.get("/api/articles")
    def api_articles(genre: str = "", tag: str = "", lang: str = ""):
        storage = _storage()
        try:
            articles = storage.get_all()
            if genre:
                articles = [a for a in articles if a.genre == genre]
            if tag:
                articles = [a for a in articles if tag in a.tags]
            if lang:
                for a in articles:
                    a.translations = storage.get_translations(a.id)
            return [a.model_dump(mode="json") for a in articles]
        finally:
            storage.close()

    return app


def _get_available_languages(storage: Storage) -> list[str]:
    """Get distinct language codes from translations table."""
    try:
        rows = storage._db.execute(
            "SELECT DISTINCT lang FROM translations ORDER BY lang"
        ).fetchall()
        return [row["lang"] for row in rows]
    except Exception:
        return []
