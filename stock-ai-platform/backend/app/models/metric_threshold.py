"""Metric thresholds.

Resolution order is user-for-stock, user, sector, country, then global.
`operator` uses the same comparison labels as the alert enum. A threshold is a
screening rule, not a trade instruction.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Index, Numeric, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.core.database import Base
from app.metrics import DEFINITION_VERSION
from app.models.enums import ALERT_OPERATOR, METRIC_SCOPE, AlertOperator, MetricScope
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin, uuid_fk

if TYPE_CHECKING:
    from app.models.stock import Stock
    from app.models.user import User


class MetricThreshold(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "metric_thresholds"
    __table_args__ = (
        Index(
            "ix_metric_thresholds_metric_scope_country_sector",
            "metric_name",
            "scope",
            "country",
            "sector",
        ),
        Index("ix_metric_thresholds_user_id", "user_id"),
        Index("ix_metric_thresholds_metric_active", "metric_name", "is_active"),
        CheckConstraint(
            "("
            "scope = 'global' AND sector IS NULL AND country IS NULL AND user_id IS NULL AND stock_id IS NULL"
            ") OR ("
            "scope = 'country' AND country IS NOT NULL AND sector IS NULL AND user_id IS NULL AND stock_id IS NULL"
            ") OR ("
            "scope = 'sector' AND sector IS NOT NULL AND user_id IS NULL AND stock_id IS NULL"
            ") OR ("
            "scope = 'user' AND user_id IS NOT NULL AND sector IS NULL AND country IS NULL"
            ")",
            name="scope_fields",
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from",
            name="effective_range",
        ),
        CheckConstraint("basis IN ('absolute', 'sector_benchmark')", name="basis_values"),
    )

    metric_name: Mapped[str] = mapped_column(String(64), nullable=False)
    scope: Mapped[MetricScope] = mapped_column(METRIC_SCOPE, nullable=False)
    sector: Mapped[str | None] = mapped_column(String(128))
    country: Mapped[str | None] = mapped_column(String(2))
    user_id: Mapped[uuid.UUID | None] = uuid_fk("users.id", ondelete="CASCADE", nullable=True)
    stock_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("stocks.id", ondelete="CASCADE"),
        nullable=True,
    )
    operator: Mapped[AlertOperator] = mapped_column(ALERT_OPERATOR, nullable=False)
    basis: Mapped[str] = mapped_column(String(32), nullable=False, default="absolute", server_default=text("'absolute'"))
    threshold_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    threshold_high: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    description: Mapped[str | None] = mapped_column(Text)
    definition_version: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=DEFINITION_VERSION,
        server_default=text(f"'{DEFINITION_VERSION}'"),
    )
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    user: Mapped[User | None] = relationship()
    stock: Mapped[Stock | None] = relationship()
