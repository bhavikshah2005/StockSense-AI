"""Point-in-time valuation. These figures move when the price moves.

Multiples are raw. Dividend yield is percentage points (1.5 means 1.5%).
Money is an absolute amount in `currency`.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Index, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin, uuid_fk

if TYPE_CHECKING:
    from app.models.stock import Stock

RATIO = Numeric(18, 6)
MONEY = Numeric(20, 2)


class ValuationSnapshot(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "valuation_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "stock_id",
            "snapshot_at",
            "source",
            name="uq_valuation_snapshots_stock_time_source",
        ),
        Index("ix_valuation_snapshots_stock_id_snapshot_at", "stock_id", "snapshot_at"),
        CheckConstraint("char_length(currency) = 3", name="currency_code"),
        CheckConstraint("currency = upper(currency)", name="currency_upper"),
    )

    stock_id: Mapped[uuid.UUID] = uuid_fk("stocks.id", ondelete="CASCADE")
    snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    market_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    market_cap: Mapped[Decimal | None] = mapped_column(MONEY)
    enterprise_value: Mapped[Decimal | None] = mapped_column(MONEY)
    pe_ratio: Mapped[Decimal | None] = mapped_column(RATIO)
    pb_ratio: Mapped[Decimal | None] = mapped_column(RATIO)
    peg_ratio: Mapped[Decimal | None] = mapped_column(RATIO)
    ev_to_ebitda: Mapped[Decimal | None] = mapped_column(RATIO)
    ev_to_sales: Mapped[Decimal | None] = mapped_column(RATIO)
    dividend_yield: Mapped[Decimal | None] = mapped_column(RATIO)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    stock: Mapped[Stock] = relationship(back_populates="valuations")
