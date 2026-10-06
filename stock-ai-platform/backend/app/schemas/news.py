from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class NewsStockLink(BaseModel):
    stock_id: UUID
    symbol: str
    exchange: str
    company_name: str
    match_method: str


class NewsCard(BaseModel):
    id: UUID
    title: str
    summary: str | None
    source: str
    url: str
    author: str | None
    published_at: datetime
    ingested_at: datetime
    language: str | None
    sentiment: str | None
    sentiment_explanation: str | None
    stocks: list[NewsStockLink]


class NewsListResponse(BaseModel):
    results: list[NewsCard]
    total: int
    limit: int
    offset: int


class SentimentDetail(BaseModel):
    classifier: str
    label: str | None
    explanation: str | None
    input_basis: str | None
    analyzed_at: datetime | None
    available: bool
    methodology: str


class NewsStatusResponse(BaseModel):
    configured: bool
    provider: str
    last_success_at: datetime | None
    last_status: str | None
    last_error: str | None
    stale: bool
    message: str


class NewsFacets(BaseModel):
    sources: list[str]
    sectors: list[str]


class NewsQuery(BaseModel):
    stock_id: UUID | None = None
    sector: str | None = Field(default=None, max_length=128)
    source: str | None = Field(default=None, max_length=255)
    sentiment: str | None = None
    published_from: datetime | None = None
    published_to: datetime | None = None
    window_days: int | None = Field(default=None, ge=1, le=90)
    limit: int = Field(default=20, ge=1, le=50)
    offset: int = Field(default=0, ge=0)
