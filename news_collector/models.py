"""Pydantic models for news articles."""

from datetime import date, datetime

from pydantic import BaseModel, Field


class Article(BaseModel):
    """A collected news article."""

    id: str = Field(description="Unique identifier (URL hash)")
    title: str = Field(description="Article title")
    url: str = Field(description="Source URL")
    source: str = Field(description="Media/publisher name")
    published_date: date | None = Field(default=None, description="Publication date")
    genre: str = Field(description="Collection genre")
    summary_raw: str = Field(default="", description="Raw summary from Gemini Grounding")
    collected_at: datetime = Field(description="Collection timestamp")

    # Populated by processor
    tags: list[str] = Field(default_factory=list, description="Auto-generated tags")
    summary: str = Field(default="", description="Gemini Flash summary")
    processed_at: datetime | None = Field(default=None, description="Processing timestamp")
    notified_at: datetime | None = Field(default=None, description="Notification timestamp")

    # Populated by get methods when translations are loaded
    translations: dict[str, "Translation"] = Field(
        default_factory=dict,
        description="Translations keyed by language code",
    )


class Translation(BaseModel):
    """A translated title and summary for a specific language."""

    article_id: str = Field(description="Parent article ID")
    lang: str = Field(description="Language code (e.g. ja, ko, zh)")
    title: str = Field(description="Translated title")
    summary: str = Field(description="Translated summary")
    translated_at: datetime = Field(description="Translation timestamp")
