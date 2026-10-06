"""Backtest request and response models."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class RunCreate(BaseModel):
    stock_id: UUID
    strategy_key: str
    strategy_version: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    start_date: date
    end_date: date
    initial_capital: Decimal
    brokerage_percent: Decimal
    slippage_bps: Decimal
    position_percent: Decimal = Decimal(100)
    stop_loss_percent: Decimal | None = None
    take_profit_percent: Decimal | None = None
    max_hold_sessions: int | None = None


class StrategyParameterResponse(BaseModel):
    name: str
    label: str
    kind: str
    minimum: int
    maximum: int
    default: int
    description: str


class StrategyResponse(BaseModel):
    key: str
    version: str
    name: str
    description: str
    holds_overnight: bool
    direction: str
    required_data: str
    entry_rule: str
    exit_rule: str
    missing_data: str
    parameters: list[StrategyParameterResponse]


class RunResponse(BaseModel):
    id: UUID
    stock_id: UUID
    symbol: str
    exchange: str
    strategy_key: str
    strategy_version: str
    parameters: dict[str, Any]
    assumptions: dict[str, Any]
    status: str
    requested_start: date
    requested_end: date
    actual_start: date | None
    actual_end: date | None
    initial_capital: str
    engine_version: str
    indicator_version: str
    detector_version: str
    data_source: str
    price_basis: str
    summary: dict[str, Any] | None
    warnings: list[str]
    error_detail: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class RunListResponse(BaseModel):
    results: list[RunResponse]
    limit: int
    offset: int


class TradeResponse(BaseModel):
    trade_number: int
    signal_at: datetime
    entry_at: datetime
    exit_at: datetime
    entry_price: str
    exit_price: str
    shares: int
    entry_charges: str
    exit_charges: str
    slippage_cost: str
    exit_reason: str
    pnl: str
    return_percent: str | None


class TradeListResponse(BaseModel):
    results: list[TradeResponse]


class EquityPointResponse(BaseModel):
    point_at: datetime
    equity: str
    drawdown_percent: str
    cash: str
    shares: int


class EquityResponse(BaseModel):
    results: list[EquityPointResponse]


class CompareResponse(BaseModel):
    left: RunResponse
    right: RunResponse
    comparable: bool
    note: str
