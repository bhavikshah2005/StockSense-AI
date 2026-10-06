"""User-owned backtest runs. Candles stay in stock_prices."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.core.database import Base
from app.models.mixins import CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin, uuid_fk

MONEY = Numeric(20, 2)
PRICE = Numeric(18, 4)


class BacktestRun(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "backtest_runs"
    __table_args__ = (
        Index("ix_backtest_runs_user_created", "user_id", "created_at"),
        Index("ix_backtest_runs_user_status", "user_id", "status"),
        CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'partial', 'insufficient_data', 'failed')",
            name="ck_backtest_runs_status",
        ),
        CheckConstraint("initial_capital > 0", name="ck_backtest_runs_capital"),
        CheckConstraint("requested_start < requested_end", name="ck_backtest_runs_range"),
    )

    user_id: Mapped[uuid.UUID] = uuid_fk("users.id", ondelete="CASCADE")
    stock_id: Mapped[uuid.UUID] = uuid_fk("stocks.id", ondelete="CASCADE")
    strategy_key: Mapped[str] = mapped_column(String(40), nullable=False)
    strategy_version: Mapped[str] = mapped_column(String(16), nullable=False)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    assumptions: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", server_default="queued")
    requested_start: Mapped[date] = mapped_column(Date, nullable=False)
    requested_end: Mapped[date] = mapped_column(Date, nullable=False)
    actual_start: Mapped[date | None] = mapped_column(Date)
    actual_end: Mapped[date | None] = mapped_column(Date)
    initial_capital: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    engine_version: Mapped[str] = mapped_column(String(32), nullable=False)
    indicator_version: Mapped[str] = mapped_column(String(32), nullable=False)
    detector_version: Mapped[str] = mapped_column(String(32), nullable=False)
    data_source: Mapped[str] = mapped_column(String(80), nullable=False)
    price_basis: Mapped[str] = mapped_column(String(32), nullable=False)
    summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    warnings: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    error_detail: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    trades: Mapped[list[BacktestTrade]] = relationship(back_populates="run", cascade="all, delete-orphan")
    equity_points: Mapped[list[BacktestEquityPoint]] = relationship(back_populates="run", cascade="all, delete-orphan")


class BacktestTrade(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "backtest_trades"
    __table_args__ = (
        Index("ix_backtest_trades_run_number", "run_id", "trade_number", unique=True),
        CheckConstraint("shares > 0", name="ck_backtest_trades_shares"),
        CheckConstraint("entry_price > 0 AND exit_price > 0", name="ck_backtest_trades_prices"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("backtest_runs.id", ondelete="CASCADE"), nullable=False)
    trade_number: Mapped[int] = mapped_column(Integer, nullable=False)
    signal_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    entry_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    exit_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    entry_price: Mapped[Decimal] = mapped_column(PRICE, nullable=False)
    exit_price: Mapped[Decimal] = mapped_column(PRICE, nullable=False)
    shares: Mapped[int] = mapped_column(Integer, nullable=False)
    entry_charges: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    exit_charges: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    slippage_cost: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    exit_reason: Mapped[str] = mapped_column(String(40), nullable=False)
    pnl: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    return_percent: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))

    run: Mapped[BacktestRun] = relationship(back_populates="trades")


class BacktestEquityPoint(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "backtest_equity_points"
    __table_args__ = (Index("ix_backtest_equity_run_time", "run_id", "point_at", unique=True),)

    run_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("backtest_runs.id", ondelete="CASCADE"), nullable=False)
    point_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    equity: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    drawdown_percent: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    cash: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    shares: Mapped[int] = mapped_column(Integer, nullable=False)

    run: Mapped[BacktestRun] = relationship(back_populates="equity_points")
