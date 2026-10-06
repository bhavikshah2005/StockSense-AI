"""Reported financial statements for one listing and one fiscal period.

Money is an absolute amount in `currency` (INR rupees, not crore or million).
Growth rates, margins, ROE, and ROCE are percentage points: 15.0 means 15%.
Debt/equity, current ratio, and interest coverage are raw ratios.

`report_date` is the period end. `filing_date` is when the result was announced,
when the provider supplies it. A null filing date means the publication time is
unknown, so the record must not be treated as known before `provider_retrieved_at`.

Valuation multiples live on `valuation_snapshots`. They move with the price.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, DateTime, Index, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin, uuid_fk

if TYPE_CHECKING:
    from app.models.stock import Stock

RATIO = Numeric(18, 6)
MONEY = Numeric(20, 2)


class Fundamental(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "fundamentals"
    __table_args__ = (
        UniqueConstraint(
            "stock_id",
            "report_date",
            "fiscal_period",
            "source",
            name="uq_fundamentals_stock_report_period_source",
        ),
        Index("ix_fundamentals_stock_id_report_date", "stock_id", "report_date"),
        CheckConstraint("fiscal_period_type IN ('annual', 'quarterly')", name="fiscal_period_type"),
        CheckConstraint("char_length(currency) = 3", name="currency_code"),
        CheckConstraint("currency = upper(currency)", name="currency_upper"),
    )

    stock_id: Mapped[uuid.UUID] = uuid_fk("stocks.id", ondelete="CASCADE")
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    fiscal_period: Mapped[str] = mapped_column(String(32), nullable=False)
    fiscal_period_type: Mapped[str] = mapped_column(String(16), nullable=False)
    filing_date: Mapped[date | None] = mapped_column(Date)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    revenue: Mapped[Decimal | None] = mapped_column(MONEY)
    revenue_growth: Mapped[Decimal | None] = mapped_column(RATIO)
    ebitda: Mapped[Decimal | None] = mapped_column(MONEY)
    ebitda_growth: Mapped[Decimal | None] = mapped_column(RATIO)
    operating_profit: Mapped[Decimal | None] = mapped_column(MONEY)
    net_income: Mapped[Decimal | None] = mapped_column(MONEY)
    profit_growth: Mapped[Decimal | None] = mapped_column(RATIO)
    eps: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    eps_growth: Mapped[Decimal | None] = mapped_column(RATIO)
    book_value_per_share: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    roe: Mapped[Decimal | None] = mapped_column(RATIO)
    roce: Mapped[Decimal | None] = mapped_column(RATIO)
    gross_margin: Mapped[Decimal | None] = mapped_column(RATIO)
    operating_margin: Mapped[Decimal | None] = mapped_column(RATIO)
    net_margin: Mapped[Decimal | None] = mapped_column(RATIO)
    debt_to_equity: Mapped[Decimal | None] = mapped_column(RATIO)
    current_ratio: Mapped[Decimal | None] = mapped_column(RATIO)
    interest_coverage: Mapped[Decimal | None] = mapped_column(RATIO)
    free_cash_flow: Mapped[Decimal | None] = mapped_column(MONEY)
    operating_cash_flow: Mapped[Decimal | None] = mapped_column(MONEY)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    stock: Mapped[Stock] = relationship(back_populates="fundamentals")
