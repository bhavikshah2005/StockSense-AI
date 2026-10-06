from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.core.database import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin, uuid_fk

if TYPE_CHECKING:
    from app.models.stock import Stock
    from app.models.user import User


class Watchlist(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "watchlists"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_watchlists_user_id_name"),
        Index("ix_watchlists_user_id", "user_id"),
    )

    user_id: Mapped[uuid.UUID] = uuid_fk("users.id", ondelete="CASCADE")
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))

    user: Mapped[User] = relationship(back_populates="watchlists")
    entries: Mapped[list[WatchlistStock]] = relationship(
        back_populates="watchlist",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class WatchlistStock(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "watchlist_stocks"
    __table_args__ = (
        UniqueConstraint(
            "watchlist_id",
            "stock_id",
            name="uq_watchlist_stocks_watchlist_id_stock_id",
        ),
        Index("ix_watchlist_stocks_stock_id", "stock_id"),
    )

    watchlist_id: Mapped[uuid.UUID] = uuid_fk("watchlists.id", ondelete="CASCADE")
    stock_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("stocks.id", ondelete="CASCADE"),
        nullable=False,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    watchlist: Mapped[Watchlist] = relationship(back_populates="entries")
    stock: Mapped[Stock] = relationship(back_populates="watchlist_entries")
