from uuid import UUID

from pydantic import BaseModel, Field


class StockSearchResult(BaseModel):
    id: UUID
    symbol: str
    company_name: str
    exchange: str
    sector: str | None
    industry: str | None
    currency: str
    country: str
    country_name: str
    isin: str | None


class StockSearchResponse(BaseModel):
    query: str
    results: list[StockSearchResult] = Field(default_factory=list)


class StockDetail(BaseModel):
    id: UUID
    symbol: str
    company_name: str
    exchange: str
    sector: str | None
    industry: str | None
    currency: str
    country: str
    country_name: str
    isin: str | None
