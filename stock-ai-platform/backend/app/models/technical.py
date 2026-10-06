"""Point-in-time technical indicators.

Named columns cover the indicators the product uses first. `additional_indicators`
holds later indicators as JSON so new names do not require a schema change.
Indicator values are nullable because a bar may not have enough history yet.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Index, Numeric, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin, uuid_fk

if TYPE_CHECKING:
    from app.models.stock import Stock

INDICATOR = Numeric(18, 6)


class TechnicalIndicator(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "technical_indicators"
    __table_args__ = (
        Index(
            "ix_technical_indicators_identity",
            "stock_id",
            "interval",
            "timestamp",
            "calculation_version",
            unique=True,
        ),
    )

    stock_id: Mapped[uuid.UUID] = uuid_fk("stocks.id", ondelete="CASCADE")
    interval: Mapped[str] = mapped_column(String(8), nullable=False, server_default="1d")
    calculation_version: Mapped[str] = mapped_column(String(32), nullable=False, server_default="indicators-1")
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    rsi_14: Mapped[Decimal | None] = mapped_column(INDICATOR)
    macd: Mapped[Decimal | None] = mapped_column(INDICATOR)
    macd_signal: Mapped[Decimal | None] = mapped_column(INDICATOR)
    macd_histogram: Mapped[Decimal | None] = mapped_column(INDICATOR)
    sma_20: Mapped[Decimal | None] = mapped_column(INDICATOR)
    sma_50: Mapped[Decimal | None] = mapped_column(INDICATOR)
    sma_100: Mapped[Decimal | None] = mapped_column(INDICATOR)
    sma_200: Mapped[Decimal | None] = mapped_column(INDICATOR)
    ema_20: Mapped[Decimal | None] = mapped_column(INDICATOR)
    ema_50: Mapped[Decimal | None] = mapped_column(INDICATOR)
    volatility: Mapped[Decimal | None] = mapped_column(INDICATOR)
    average_volume: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    additional_indicators: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    stock: Mapped[Stock] = relationship(back_populates="technical_indicators")


class TechnicalPattern(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One detected formation for a listing, interval, and detector version."""

    __tablename__ = "technical_patterns"
    __table_args__ = (
        Index(
            "uq_technical_patterns_identity",
            "stock_id",
            "interval",
            "pattern_type",
            "start_timestamp",
            "detector_version",
            unique=True,
        ),
        Index("ix_technical_patterns_stock_id_status", "stock_id", "status"),
        CheckConstraint(
            "status IN ('developing', 'confirmed', 'invalidated', 'completed', 'uncertain', 'insufficient_data')",
            name="ck_technical_patterns_status",
        ),
        CheckConstraint("interval IN ('1d', '1h', '15m', '5m')", name="ck_technical_patterns_interval"),
    )

    stock_id: Mapped[uuid.UUID] = uuid_fk("stocks.id", ondelete="CASCADE")
    pattern_type: Mapped[str] = mapped_column(String(64), nullable=False)
    direction: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    interval: Mapped[str] = mapped_column(String(8), nullable=False)
    start_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    key_levels: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    pivot_evidence: Mapped[list[object]] = mapped_column(JSONB, nullable=False, default=list)
    evidence_summary: Mapped[str] = mapped_column(String(2000), nullable=False)
    detector_version: Mapped[str] = mapped_column(String(32), nullable=False)
    source_price_as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    stock: Mapped[Stock] = relationship(back_populates="technical_patterns")
