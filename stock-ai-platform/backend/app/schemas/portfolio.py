from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_serializer


def _text(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value, "f")


class PortfolioWrite(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=280)


class PortfolioResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    currency: str
    contributed: Decimal
    cash: Decimal
    holding_count: int
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @field_serializer("contributed", "cash")
    def money(self, value: Decimal) -> str:
        return format(value, "f")


class PortfolioListResponse(BaseModel):
    results: list[PortfolioResponse]


class TransactionWrite(BaseModel):
    stock_id: UUID
    side: str = Field(pattern="^(buy|sell)$")
    quantity: Decimal = Field(gt=0)
    price: Decimal = Field(gt=0)
    charges: Decimal = Field(default=Decimal("0"), ge=0)
    traded_at: datetime
    note: str | None = Field(default=None, max_length=280)


class TransactionUpdate(BaseModel):
    quantity: Decimal = Field(gt=0)
    price: Decimal = Field(gt=0)
    charges: Decimal = Field(default=Decimal("0"), ge=0)
    traded_at: datetime
    note: str | None = Field(default=None, max_length=280)


class TransactionResponse(BaseModel):
    id: UUID
    portfolio_id: UUID
    stock_id: UUID
    symbol: str
    exchange: str
    side: str
    quantity: Decimal
    price: Decimal
    charges: Decimal
    traded_at: datetime
    note: str | None

    @field_serializer("quantity", "price", "charges")
    def money(self, value: Decimal) -> str:
        return format(value, "f")


class CashWrite(BaseModel):
    kind: str = Field(pattern="^(deposit|withdrawal)$")
    amount: Decimal = Field(gt=0)
    occurred_at: datetime
    note: str | None = Field(default=None, max_length=280)


class CashResponse(BaseModel):
    id: UUID
    kind: str
    amount: Decimal
    occurred_at: datetime
    note: str | None

    @field_serializer("amount")
    def money(self, value: Decimal) -> str:
        return format(value, "f")


class HoldingResponse(BaseModel):
    stock_id: UUID
    symbol: str
    exchange: str
    company_name: str
    sector: str | None
    quantity: Decimal
    average_cost: Decimal
    cost_basis: Decimal
    realized_pnl: Decimal
    last_price: Decimal | None
    market_value: Decimal | None
    unrealized_pnl: Decimal | None
    unrealized_pnl_percent: Decimal | None
    price_timestamp: datetime | None
    price_state: str
    delayed: bool | None
    delay_minutes: int | None

    @field_serializer(
        "quantity",
        "average_cost",
        "cost_basis",
        "realized_pnl",
        "last_price",
        "market_value",
        "unrealized_pnl",
        "unrealized_pnl_percent",
    )
    def money(self, value: Decimal | None) -> str | None:
        return _text(value)


class AllocationSlice(BaseModel):
    symbol: str | None = None
    stock_id: UUID | None = None
    sector: str | None = None
    market_value: Decimal
    weight_percent: Decimal

    @field_serializer("market_value", "weight_percent")
    def money(self, value: Decimal) -> str:
        return format(value, "f")


class AllocationResponse(BaseModel):
    status: str
    by_stock: list[AllocationSlice]
    by_sector: list[AllocationSlice]
    unpriced_symbols: list[str]


class ValuationResponse(BaseModel):
    portfolio_id: UUID
    currency: str
    cash: Decimal
    contributed: Decimal
    cost_basis: Decimal
    market_value: Decimal | None
    realized_pnl: Decimal
    unrealized_pnl: Decimal | None
    total_pnl: Decimal | None
    valuation_complete: bool
    holdings_only: bool
    basis: str
    benchmark: None
    benchmark_note: str
    as_of: datetime
    holdings: list[HoldingResponse]
    allocation: AllocationResponse

    @field_serializer("cash", "contributed", "cost_basis", "market_value", "realized_pnl", "unrealized_pnl", "total_pnl")
    def money(self, value: Decimal | None) -> str | None:
        return _text(value)


class HistoryPoint(BaseModel):
    date: str
    holdings_value: Decimal

    @field_serializer("holdings_value")
    def money(self, value: Decimal) -> str:
        return format(value, "f")


class HistoryResponse(BaseModel):
    status: str
    message: str
    points: list[HistoryPoint]


class RiskSettingsWrite(BaseModel):
    capital_inr: Decimal | None = Field(default=None, ge=0)
    max_risk_inr: Decimal | None = Field(default=None, gt=0)
    max_risk_percent: Decimal | None = Field(default=None, gt=0, le=100)
    max_allocation_percent: Decimal | None = Field(default=None, gt=0, le=100)
    max_shares: int | None = Field(default=None, ge=1, le=1_000_000_000)


class RiskSettingsResponse(BaseModel):
    capital_inr: Decimal | None
    max_risk_inr: Decimal | None
    max_risk_percent: Decimal | None
    max_allocation_percent: Decimal | None
    max_shares: int | None

    @field_serializer("capital_inr", "max_risk_inr", "max_risk_percent", "max_allocation_percent")
    def money(self, value: Decimal | None) -> str | None:
        return _text(value)


class SizeRequest(BaseModel):
    capital: Decimal = Field(gt=0)
    entry: Decimal = Field(gt=0)
    stop: Decimal = Field(gt=0)
    max_risk_inr: Decimal | None = Field(default=None, gt=0)
    max_risk_percent: Decimal | None = Field(default=None, gt=0, le=100)
    max_allocation_percent: Decimal | None = Field(default=None, gt=0, le=100)
    max_shares: int | None = Field(default=None, ge=1, le=1_000_000_000)


class SizeResponse(BaseModel):
    quantity: int
    position_value: Decimal
    per_share_risk: Decimal
    total_risk: Decimal
    capital_utilization_percent: Decimal
    binding_constraint: str
    risk_amount: Decimal
    assumptions: str
    warning: str

    @field_serializer("position_value", "per_share_risk", "total_risk", "capital_utilization_percent", "risk_amount")
    def money(self, value: Decimal) -> str:
        return format(value, "f")
