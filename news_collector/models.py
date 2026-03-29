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
