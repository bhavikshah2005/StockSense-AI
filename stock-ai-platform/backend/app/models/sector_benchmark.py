"""Sector-level metric snapshots used later for relative comparison.

Units match `fundamentals`: multiples are raw, and rates are percentage points.
There is no foreign key to `stocks`; a stock is compared by its sector and country.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin

RATIO = Numeric(18, 6)


class SectorBenchmark(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "sector_benchmarks"
    __table_args__ = (
        Index(
            "ix_sector_benchmarks_sector_country_calculation_date",
            "sector",
            "country",
            "calculation_date",
            unique=True,
        ),
        Index("ix_sector_benchmarks_country", "country"),
    )

    sector: Mapped[str] = mapped_column(String(128), nullable=False)
    country: Mapped[str] = mapped_column(String(2), nullable=False)
    calculation_date: Mapped[date] = mapped_column(Date, nullable=False)
    pe_ratio: Mapped[Decimal | None] = mapped_column(RATIO)
    pb_ratio: Mapped[Decimal | None] = mapped_column(RATIO)
    roe: Mapped[Decimal | None] = mapped_column(RATIO)
    roce: Mapped[Decimal | None] = mapped_column(RATIO)
    net_margin: Mapped[Decimal | None] = mapped_column(RATIO)
    revenue_growth: Mapped[Decimal | None] = mapped_column(RATIO)
    debt_to_equity: Mapped[Decimal | None] = mapped_column(RATIO)
    dividend_yield: Mapped[Decimal | None] = mapped_column(RATIO)
    currency: Mapped[str | None] = mapped_column(String(3))
    source: Mapped[str | None] = mapped_column(String(64))
    methodology: Mapped[str | None] = mapped_column(String(255))
