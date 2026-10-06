"""Technical analysis responses. Prices are decimal strings."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class TechnicalStock(BaseModel):
    id: UUID
    symbol: str
    exchange: str
    company_name: str


class IndicatorBlock(BaseModel):
    rsi_14: str | None
    macd: str | None
    macd_signal: str | None
    macd_histogram: str | None
    sma_20: str | None
    sma_50: str | None
    sma_100: str | None
    sma_200: str | None
    ema_20: str | None
    ema_50: str | None
    volatility: str | None
    average_volume: str | None
    volume: int | None
    week52_high: str | None
    week52_low: str | None
    distance_from_high_percent: str | None
    distance_from_low_percent: str | None
    performance: dict[str, str | None]
    as_of: datetime | None


class SeriesPoint(BaseModel):
    timestamp: datetime
    close: str
    sma_20: str | None
    sma_50: str | None
    volume: int | None


class PivotPoint(BaseModel):
    timestamp: datetime
    confirmed_at: datetime
    kind: str
    price: str


class BoundaryPoint(BaseModel):
    timestamp: datetime
    price: str


class PatternBlock(BaseModel):
    pattern_type: str
    direction: str
    status: str
    start_timestamp: datetime
    end_timestamp: datetime
    levels: dict[str, str]
    boundaries: dict[str, list[BoundaryPoint]]
    pivots: list[PivotPoint]
    confirmation_met: bool
    confirmation_timestamp: datetime | None
    invalidation: str
    evidence: str
    limitations: list[str]
    quality: str
    detector_version: str
    definition: str


class ZoneBlock(BaseModel):
    kind: str
    lower: str
    upper: str
    tests: int
    last_test: datetime | None
    status: str
    method: str


class BreakoutBlock(BaseModel):
    source: str
    side: str
    status: str
    boundary: str
    confirmation_met: bool
    volume_evidence: str
    missing: list[str]


class ConclusionBlock(BaseModel):
    category: str
    text: str
    conflicts: list[str]
    invalidation: list[str]


class TechnicalAnalysisResponse(BaseModel):
    stock: TechnicalStock
    interval: str
    freshness: str
    price_as_of: datetime | None
    calculated_at: datetime
    indicators: IndicatorBlock
    series: list[SeriesPoint]
    patterns: list[PatternBlock]
    zones: list[ZoneBlock]
    breakouts: list[BreakoutBlock]
    conclusion: ConclusionBlock
    limitations: list[str]
    indicator_version: str
    detector_version: str


class PatternHistoryResponse(BaseModel):
    stock: TechnicalStock
    interval: str
    total: int
    limit: int
    offset: int
    results: list[PatternBlock]


class TechnicalSummaryResponse(BaseModel):
    stock: TechnicalStock
    interval: str
    freshness: str
    price_as_of: datetime | None
    calculated_at: datetime
    conclusion: ConclusionBlock
    limitations: list[str]
