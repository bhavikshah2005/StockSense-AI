from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_serializer


class QuoteResponse(BaseModel):
    """Latest quote. Money is serialized as a decimal string."""

    model_config = ConfigDict()

    stock_id: UUID
    symbol: str
    exchange: str
    currency: str
    current_price: Decimal
    previous_close: Decimal | None
    change: Decimal | None
    change_percent: Decimal | None
    open: Decimal | None
    high: Decimal | None
    low: Decimal | None
    volume: int | None
    market_timestamp: datetime
    fetched_at: datetime
    delayed: bool
    delay_minutes: int | None

    @field_serializer(
        "current_price",
        "previous_close",
        "change",
        "change_percent",
        "open",
        "high",
        "low",
        when_used="json",
    )
    def serialize_money(self, value: Decimal | None) -> str | None:
        if value is None:
            return None
        return format(value, "f")


class PriceBarResponse(BaseModel):
    stock_id: UUID
    timestamp: datetime
    interval: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    adjusted_close: Decimal | None
    volume: int

    @field_serializer("open", "high", "low", "close", "adjusted_close", when_used="json")
    def serialize_money(self, value: Decimal | None) -> str | None:
        if value is None:
            return None
        return format(value, "f")


class PriceHistoryResponse(BaseModel):
    stock_id: UUID
    interval: str
    bars: list[PriceBarResponse]


class HistoryStock(BaseModel):
    id: UUID
    symbol: str
    company_name: str
    exchange: str
    currency: str


class HistoryBar(BaseModel):
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    adjusted_close: Decimal | None
    volume: int

    @field_serializer("open", "high", "low", "close", "adjusted_close", when_used="json")
    def serialize_money(self, value: Decimal | None) -> str | None:
        if value is None:
            return None
        return format(value, "f")


class HistoryPerformance(BaseModel):
    start_price: Decimal
    end_price: Decimal
    change: Decimal
    change_percent: Decimal

    @field_serializer("start_price", "end_price", "change", "change_percent", when_used="json")
    def serialize_money(self, value: Decimal) -> str:
        return format(value, "f")


class HistoryResponse(BaseModel):
    stock: HistoryStock
    interval: str
    range: str | None
    start_date: date
    end_date: date
    market_timestamp: datetime | None
    fetched_at: datetime
    data: list[HistoryBar]
    performance: HistoryPerformance | None
    period_high: Decimal | None
    period_low: Decimal | None

    @field_serializer("period_high", "period_low", when_used="json")
    def serialize_extremes(self, value: Decimal | None) -> str | None:
        if value is None:
            return None
        return format(value, "f")


class MarketStatusResponse(BaseModel):
    exchange: str
    status: str
    observed_at: datetime
    source: str
