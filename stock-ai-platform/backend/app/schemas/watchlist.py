"""Watchlist responses. Quotes are omitted when the market-data service has no price."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class WatchlistCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)


class WatchlistUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=500)


class WatchlistStockCreate(BaseModel):
    stock_id: UUID


class WatchlistOrderUpdate(BaseModel):
    stock_ids: list[UUID] = Field(min_length=1, max_length=100)


class WatchlistSummary(BaseModel):
    id: UUID
    name: str
    description: str | None
    is_default: bool
    stock_count: int
    contains_stock: bool | None
    created_at: datetime
    updated_at: datetime


class WatchlistListResponse(BaseModel):
    results: list[WatchlistSummary]


class WatchlistQuote(BaseModel):
    available: bool
    delayed: bool | None
    source: str | None
    currency: str | None
    current_price: str | None
    previous_close: str | None
    change: str | None
    change_percent: str | None
    market_timestamp: datetime | None
    fetched_at: datetime | None


class WatchlistEntry(BaseModel):
    stock_id: UUID
    company_name: str
    symbol: str
    exchange: str
    isin: str | None
    sector: str | None
    industry: str | None
    sort_order: int
    added_at: datetime
    quote: WatchlistQuote


class WatchlistDetail(BaseModel):
    id: UUID
    name: str
    description: str | None
    is_default: bool
    stock_count: int
    created_at: datetime
    updated_at: datetime
    stocks: list[WatchlistEntry]
