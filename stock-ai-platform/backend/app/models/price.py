"""OHLCV bars.

`interval` separates 1d, 1h, 15m, and 5m bars that share a timestamp.
`timestamp` is timezone-aware.
Prices use numeric values. Volume is a share count.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin, uuid_fk

if TYPE_CHECKING:
    from app.models.stock import Stock


class StockPrice(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "stock_prices"
    __table_args__ = (
        Index(
            "ix_stock_prices_stock_interval_timestamp",
            "stock_id",
            "interval",
            "timestamp",
            unique=True,
        ),
        Index("ix_stock_prices_timestamp", "timestamp"),
        CheckConstraint("high >= low", name="high_gte_low"),
        CheckConstraint("volume >= 0", name="volume_nonnegative"),
        CheckConstraint(
            "open >= 0 AND high >= 0 AND low >= 0 AND close >= 0",
            name="prices_nonnegative",
        ),
        CheckConstraint(
            "adjusted_close IS NULL OR adjusted_close >= 0",
            name="adjusted_close_nonnegative",
        ),
        CheckConstraint("interval IN ('1d', '1h', '15m', '5m')", name="interval_known"),
    )

    stock_id: Mapped[uuid.UUID] = uuid_fk("stocks.id", ondelete="CASCADE")
    interval: Mapped[str] = mapped_column(String(8), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    open: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    adjusted_close: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)

    stock: Mapped[Stock] = relationship(back_populates="prices")
