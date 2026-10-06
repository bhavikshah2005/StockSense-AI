"""User portfolios, transactions, and derived holdings.

Transactions and cash movements are the records. Holding quantity and
average cost are rewritten from those records. Market value is not stored.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.types import Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin, uuid_fk

if TYPE_CHECKING:
    from app.models.stock import Stock
    from app.models.user import User

MONEY = Numeric(20, 2)
PRICE = Numeric(18, 4)
QUANTITY = Numeric(20, 8)


class Portfolio(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "portfolios"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_portfolios_user_id_name"),
        Index("ix_portfolios_user_id", "user_id"),
        CheckConstraint("total_capital >= 0", name="total_capital_nonnegative"),
        CheckConstraint("available_cash >= 0", name="available_cash_nonnegative"),
        CheckConstraint("currency = 'INR'", name="currency_inr"),
    )

    user_id: Mapped[uuid.UUID] = uuid_fk("users.id", ondelete="CASCADE")
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR", server_default=text("'INR'"))
    total_capital: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=Decimal("0"), server_default=text("0"))
    available_cash: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=Decimal("0"), server_default=text("0"))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="portfolios")
    holdings: Mapped[list[PortfolioHolding]] = relationship(back_populates="portfolio", cascade="all, delete-orphan", passive_deletes=True)
    transactions: Mapped[list[PortfolioTransaction]] = relationship(back_populates="portfolio", cascade="all, delete-orphan", passive_deletes=True)
    cash_movements: Mapped[list[PortfolioCashMovement]] = relationship(back_populates="portfolio", cascade="all, delete-orphan", passive_deletes=True)


class PortfolioHolding(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "portfolio_holdings"
    __table_args__ = (
        UniqueConstraint("portfolio_id", "stock_id", name="uq_portfolio_holdings_portfolio_id_stock_id"),
        Index("ix_portfolio_holdings_stock_id", "stock_id"),
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("average_buy_price >= 0", name="average_buy_price_nonnegative"),
        CheckConstraint("cost_basis >= 0", name="cost_basis_nonnegative"),
    )

    portfolio_id: Mapped[uuid.UUID] = uuid_fk("portfolios.id", ondelete="CASCADE")
    stock_id: Mapped[uuid.UUID] = uuid_fk("stocks.id", ondelete="RESTRICT")
    quantity: Mapped[Decimal] = mapped_column(QUANTITY, nullable=False)
    average_buy_price: Mapped[Decimal] = mapped_column(PRICE, nullable=False)
    cost_basis: Mapped[Decimal] = mapped_column(MONEY, nullable=False)

    portfolio: Mapped[Portfolio] = relationship(back_populates="holdings")
    stock: Mapped[Stock] = relationship(back_populates="portfolio_holdings")


class PortfolioTransaction(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "portfolio_transactions"
    __table_args__ = (
        Index("ix_portfolio_transactions_portfolio_traded", "portfolio_id", "traded_at"),
        Index("ix_portfolio_transactions_stock_id", "stock_id"),
        CheckConstraint("side IN ('buy', 'sell')", name="side_known"),
        CheckConstraint("quantity > 0 AND quantity = trunc(quantity)", name="whole_shares"),
        CheckConstraint("price > 0", name="price_positive"),
        CheckConstraint("charges >= 0", name="charges_nonnegative"),
    )

    portfolio_id: Mapped[uuid.UUID] = uuid_fk("portfolios.id", ondelete="CASCADE")
    stock_id: Mapped[uuid.UUID] = uuid_fk("stocks.id", ondelete="RESTRICT")
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(QUANTITY, nullable=False)
    price: Mapped[Decimal] = mapped_column(PRICE, nullable=False)
    charges: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=Decimal("0"), server_default=text("0"))
    traded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)

    portfolio: Mapped[Portfolio] = relationship(back_populates="transactions")
    stock: Mapped[Stock] = relationship()


class PortfolioCashMovement(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "portfolio_cash_movements"
    __table_args__ = (
        Index("ix_portfolio_cash_movements_portfolio_occurred", "portfolio_id", "occurred_at"),
        CheckConstraint("kind IN ('deposit', 'withdrawal')", name="kind_known"),
        CheckConstraint("amount > 0", name="amount_positive"),
    )

    portfolio_id: Mapped[uuid.UUID] = uuid_fk("portfolios.id", ondelete="CASCADE")
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)

    portfolio: Mapped[Portfolio] = relationship(back_populates="cash_movements")


class UserRiskSettings(Base, TimestampMixin):
    __tablename__ = "user_risk_settings"
    __table_args__ = (
        CheckConstraint("capital_inr IS NULL OR capital_inr >= 0", name="capital_nonnegative"),
        CheckConstraint("max_risk_inr IS NULL OR max_risk_inr > 0", name="risk_inr_positive"),
        CheckConstraint("max_risk_percent IS NULL OR (max_risk_percent > 0 AND max_risk_percent <= 100)", name="risk_percent_range"),
        CheckConstraint(
            "max_allocation_percent IS NULL OR (max_allocation_percent > 0 AND max_allocation_percent <= 100)",
            name="allocation_percent_range",
        ),
        CheckConstraint("max_shares IS NULL OR max_shares >= 1", name="max_shares_positive"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    capital_inr: Mapped[Decimal | None] = mapped_column(MONEY)
    max_risk_inr: Mapped[Decimal | None] = mapped_column(MONEY)
    max_risk_percent: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    max_allocation_percent: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    max_shares: Mapped[int | None] = mapped_column(Integer)
