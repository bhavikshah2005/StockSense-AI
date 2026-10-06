"""User-owned alert rules, trigger history, and in-app notifications.

Trigger events stay in `alert_events`. Read state lives on `notifications`, so
marking a notification read does not remove the event.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.core.database import Base
from app.models.enums import ALERT_OPERATOR, THRESHOLD_TYPE, AlertOperator, ThresholdType
from app.models.mixins import CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin, uuid_fk

if TYPE_CHECKING:
    from app.models.stock import Stock
    from app.models.user import User

THRESHOLD = Numeric(20, 6)


class Alert(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "alerts"
    __table_args__ = (
        Index("ix_alerts_user_id", "user_id"),
        Index("ix_alerts_user_id_is_active", "user_id", "is_active"),
        Index("ix_alerts_stock_id", "stock_id"),
        Index("ix_alerts_status", "status"),
        CheckConstraint(
            "status IN ('active', 'paused', 'triggered', 'disabled')",
            name="ck_alerts_status",
        ),
        CheckConstraint("repeat_mode IN ('once', 'repeat')", name="ck_alerts_repeat_mode"),
        CheckConstraint(
            "category IN ('price', 'fundamental', 'technical', 'pattern')",
            name="ck_alerts_category",
        ),
        CheckConstraint(
            "(status = 'active' AND is_active) OR (status <> 'active' AND NOT is_active)",
            name="ck_alerts_status_active",
        ),
    )

    user_id: Mapped[uuid.UUID] = uuid_fk("users.id", ondelete="CASCADE")
    stock_id: Mapped[uuid.UUID] = uuid_fk("stocks.id", ondelete="CASCADE")
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    metric: Mapped[str] = mapped_column(String(64), nullable=False)
    operator: Mapped[AlertOperator] = mapped_column(ALERT_OPERATOR, nullable=False)
    threshold_type: Mapped[ThresholdType] = mapped_column(THRESHOLD_TYPE, nullable=False)
    threshold_value: Mapped[Decimal | None] = mapped_column(THRESHOLD)
    threshold_high: Mapped[Decimal | None] = mapped_column(THRESHOLD)
    sector_adjusted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    pattern_type: Mapped[str | None] = mapped_column(String(64))
    pattern_status: Mapped[str | None] = mapped_column(String(32))
    percent_interval: Mapped[str | None] = mapped_column(String(8))
    repeat_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="once", server_default=text("'once'"))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active", server_default=text("'active'"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    armed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    arm_generation: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=text("1"))
    note: Mapped[str | None] = mapped_column(String(280))
    last_evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_data_status: Mapped[str | None] = mapped_column(String(32))
    last_value: Mapped[Decimal | None] = mapped_column(THRESHOLD)
    previous_value: Mapped[Decimal | None] = mapped_column(THRESHOLD)
    last_pattern_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    last_pattern_status: Mapped[str | None] = mapped_column(String(32))

    user: Mapped[User] = relationship(back_populates="alerts")
    stock: Mapped[Stock] = relationship(back_populates="alerts")
    events: Mapped[list[AlertEvent]] = relationship(
        back_populates="alert",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class AlertEvent(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "alert_events"
    __table_args__ = (
        Index("ix_alert_events_alert_id", "alert_id"),
        Index("ix_alert_events_stock_id_triggered_at", "stock_id", "triggered_at"),
        Index("ix_alert_events_user_id_triggered_at", "user_id", "triggered_at"),
        Index("uq_alert_events_idempotency", "idempotency_key", unique=True),
    )

    alert_id: Mapped[uuid.UUID] = uuid_fk("alerts.id", ondelete="CASCADE")
    user_id: Mapped[uuid.UUID] = uuid_fk("users.id", ondelete="CASCADE")
    stock_id: Mapped[uuid.UUID] = uuid_fk("stocks.id", ondelete="CASCADE")
    triggered_value: Mapped[Decimal] = mapped_column(THRESHOLD, nullable=False)
    previous_value: Mapped[Decimal | None] = mapped_column(THRESHOLD)
    threshold_value: Mapped[Decimal] = mapped_column(THRESHOLD, nullable=False)
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    message: Mapped[str] = mapped_column(Text, nullable=False)
    data_status: Mapped[str] = mapped_column(String(32), nullable=False, default="fresh", server_default=text("'fresh'"))
    source: Mapped[str | None] = mapped_column(String(64))
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))

    alert: Mapped[Alert] = relationship(back_populates="events")
    stock: Mapped[Stock] = relationship(back_populates="alert_events")
    notification: Mapped[Notification | None] = relationship(back_populates="event", cascade="all, delete-orphan")


class Notification(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user_id_created_at", "user_id", "created_at"),
        Index("uq_notifications_alert_event_id", "alert_event_id", unique=True),
    )

    user_id: Mapped[uuid.UUID] = uuid_fk("users.id", ondelete="CASCADE")
    alert_event_id: Mapped[uuid.UUID] = uuid_fk("alert_events.id", ondelete="CASCADE")
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    event: Mapped[AlertEvent] = relationship(back_populates="notification")


class NotificationPreference(Base, TimestampMixin):
    __tablename__ = "notification_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    in_app_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
