from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, Index, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.ai_analysis import AiAnalysis
    from app.models.alert import Alert, AlertEvent
    from app.models.fundamental import Fundamental
    from app.models.valuation import ValuationSnapshot
    from app.models.news import NewsArticle, NewsArticleStock
    from app.models.portfolio import PortfolioHolding
    from app.models.price import StockPrice
    from app.models.technical import TechnicalIndicator, TechnicalPattern
    from app.models.watchlist import WatchlistStock


class Stock(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A listed instrument. Exchange and country are independent.

    `country` is an ISO 3166-1 alpha-2 code. `currency` is an ISO 4217 code.
    Sector benchmarks are matched later by sector and country, not by a foreign key,
    because a benchmark is a dated aggregate rather than a parent of the stock.
    """

    __tablename__ = "stocks"
    __table_args__ = (
        UniqueConstraint("symbol", "exchange", name="uq_stocks_symbol_exchange"),
        Index("ix_stocks_symbol", "symbol"),
        Index("ix_stocks_sector", "sector"),
        Index("ix_stocks_isin", "isin"),
        CheckConstraint("char_length(country) = 2", name="country_code"),
        CheckConstraint("isin IS NULL OR char_length(isin) = 12", name="isin_length"),
        CheckConstraint("char_length(currency) = 3", name="currency_code"),
        CheckConstraint("country = upper(country)", name="country_upper"),
        CheckConstraint("currency = upper(currency)", name="currency_upper"),
    )

    symbol: Mapped[str] = mapped_column(String(64), nullable=False)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    exchange: Mapped[str] = mapped_column(String(32), nullable=False)
    country: Mapped[str] = mapped_column(String(2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    sector: Mapped[str | None] = mapped_column(String(128))
    industry: Mapped[str | None] = mapped_column(String(128))
    isin: Mapped[str | None] = mapped_column(String(12))
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    prices: Mapped[list[StockPrice]] = relationship(
        back_populates="stock",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    valuations: Mapped[list[ValuationSnapshot]] = relationship(
        back_populates="stock",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    fundamentals: Mapped[list[Fundamental]] = relationship(
        back_populates="stock",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    technical_indicators: Mapped[list[TechnicalIndicator]] = relationship(
        back_populates="stock",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    technical_patterns: Mapped[list[TechnicalPattern]] = relationship(
        back_populates="stock",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    news_articles: Mapped[list[NewsArticle]] = relationship(back_populates="stock")
    news_links: Mapped[list[NewsArticleStock]] = relationship(back_populates="stock")
    alerts: Mapped[list[Alert]] = relationship(
        back_populates="stock",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    alert_events: Mapped[list[AlertEvent]] = relationship(
        back_populates="stock",
        passive_deletes=True,
    )
    portfolio_holdings: Mapped[list[PortfolioHolding]] = relationship(back_populates="stock")
    ai_analyses: Mapped[list[AiAnalysis]] = relationship(
        back_populates="stock",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    watchlist_entries: Mapped[list[WatchlistStock]] = relationship(
        back_populates="stock",
        passive_deletes=True,
    )
