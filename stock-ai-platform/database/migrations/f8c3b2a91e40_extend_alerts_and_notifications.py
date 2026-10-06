"""extend alerts with lifecycle, events, and in-app notifications

Revision ID: f8c3b2a91e40
Revises: e5b1a8c34d70
Create Date: 2026-09-24 23:40:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "f8c3b2a91e40"
down_revision: Union[str, Sequence[str], None] = "e5b1a8c34d70"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("alerts", sa.Column("category", sa.String(length=32), nullable=True))
    op.add_column("alerts", sa.Column("threshold_high", sa.Numeric(20, 6), nullable=True))
    op.add_column("alerts", sa.Column("pattern_type", sa.String(length=64), nullable=True))
    op.add_column("alerts", sa.Column("pattern_status", sa.String(length=32), nullable=True))
    op.add_column("alerts", sa.Column("percent_interval", sa.String(length=8), nullable=True))
    op.add_column("alerts", sa.Column("repeat_mode", sa.String(length=16), server_default="once", nullable=False))
    op.add_column("alerts", sa.Column("status", sa.String(length=16), server_default="active", nullable=False))
    op.add_column("alerts", sa.Column("armed", sa.Boolean(), server_default=sa.text("true"), nullable=False))
    op.add_column("alerts", sa.Column("arm_generation", sa.Integer(), server_default="1", nullable=False))
    op.add_column("alerts", sa.Column("note", sa.String(length=280), nullable=True))
    op.add_column("alerts", sa.Column("last_evaluated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("alerts", sa.Column("last_data_status", sa.String(length=32), nullable=True))
    op.add_column("alerts", sa.Column("last_value", sa.Numeric(20, 6), nullable=True))
    op.add_column("alerts", sa.Column("previous_value", sa.Numeric(20, 6), nullable=True))
    op.add_column("alerts", sa.Column("last_pattern_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("alerts", sa.Column("last_pattern_status", sa.String(length=32), nullable=True))
    op.execute("ALTER TABLE alerts ALTER COLUMN threshold_value DROP NOT NULL")
    op.execute(
        """
        UPDATE alerts
        SET category = CASE
            WHEN metric IN ('price', 'price_change_percent') THEN 'price'
            WHEN metric LIKE '%pattern%' THEN 'pattern'
            ELSE 'fundamental'
        END
        WHERE category IS NULL
        """
    )
    op.execute("UPDATE alerts SET status = CASE WHEN is_active THEN 'active' ELSE 'paused' END")
    op.alter_column("alerts", "category", nullable=False)
    op.execute(
        "ALTER TABLE alerts ADD CONSTRAINT ck_alerts_status CHECK (status IN ('active', 'paused', 'triggered', 'disabled'))"
    )
    op.execute("ALTER TABLE alerts ADD CONSTRAINT ck_alerts_repeat_mode CHECK (repeat_mode IN ('once', 'repeat'))")
    op.execute(
        "ALTER TABLE alerts ADD CONSTRAINT ck_alerts_category CHECK (category IN ('price', 'fundamental', 'technical', 'pattern'))"
    )
    op.execute(
        "ALTER TABLE alerts ADD CONSTRAINT ck_alerts_status_active CHECK ((status = 'active' AND is_active) OR (status <> 'active' AND NOT is_active))"
    )
    op.create_index("ix_alerts_status", "alerts", ["status"])

    op.add_column("alert_events", sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("alert_events", sa.Column("previous_value", sa.Numeric(20, 6), nullable=True))
    op.add_column("alert_events", sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("alert_events", sa.Column("data_status", sa.String(length=32), server_default="fresh", nullable=False))
    op.add_column("alert_events", sa.Column("source", sa.String(length=64), nullable=True))
    op.add_column("alert_events", sa.Column("idempotency_key", sa.String(length=200), nullable=True))
    op.execute(
        """
        UPDATE alert_events AS event
        SET user_id = alert.user_id
        FROM alerts AS alert
        WHERE event.alert_id = alert.id AND event.user_id IS NULL
        """
    )
    op.execute("DELETE FROM alert_events WHERE user_id IS NULL")
    op.execute("UPDATE alert_events SET idempotency_key = id::text WHERE idempotency_key IS NULL")
    op.alter_column("alert_events", "user_id", nullable=False)
    op.alter_column("alert_events", "idempotency_key", nullable=False)
    op.create_foreign_key(
        "fk_alert_events_user_id_users",
        "alert_events",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_alert_events_user_id_triggered_at", "alert_events", ["user_id", "triggered_at"])
    op.create_index("uq_alert_events_idempotency", "alert_events", ["idempotency_key"], unique=True)

    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("alert_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["alert_event_id"], ["alert_events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("alert_event_id", name="uq_notifications_alert_event_id"),
    )
    op.create_index("ix_notifications_user_id_created_at", "notifications", ["user_id", "created_at"])
    op.create_table(
        "notification_preferences",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("in_app_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade() -> None:
    op.drop_table("notification_preferences")
    op.drop_index("ix_notifications_user_id_created_at", table_name="notifications")
    op.drop_table("notifications")
    op.drop_index("uq_alert_events_idempotency", table_name="alert_events")
    op.drop_index("ix_alert_events_user_id_triggered_at", table_name="alert_events")
    op.drop_constraint("fk_alert_events_user_id_users", "alert_events", type_="foreignkey")
    op.drop_column("alert_events", "idempotency_key")
    op.drop_column("alert_events", "source")
    op.drop_column("alert_events", "data_status")
    op.drop_column("alert_events", "observed_at")
    op.drop_column("alert_events", "previous_value")
    op.drop_column("alert_events", "user_id")
    op.drop_index("ix_alerts_status", table_name="alerts")
    op.execute("ALTER TABLE alerts DROP CONSTRAINT IF EXISTS ck_alerts_status_active")
    op.execute("ALTER TABLE alerts DROP CONSTRAINT IF EXISTS ck_alerts_category")
    op.execute("ALTER TABLE alerts DROP CONSTRAINT IF EXISTS ck_alerts_repeat_mode")
    op.execute("ALTER TABLE alerts DROP CONSTRAINT IF EXISTS ck_alerts_status")
    op.drop_column("alerts", "last_pattern_status")
    op.drop_column("alerts", "last_pattern_id")
    op.drop_column("alerts", "previous_value")
    op.drop_column("alerts", "last_value")
    op.drop_column("alerts", "last_data_status")
    op.drop_column("alerts", "last_evaluated_at")
    op.drop_column("alerts", "note")
    op.drop_column("alerts", "arm_generation")
    op.drop_column("alerts", "armed")
    op.drop_column("alerts", "status")
    op.drop_column("alerts", "repeat_mode")
    op.drop_column("alerts", "percent_interval")
    op.drop_column("alerts", "pattern_status")
    op.drop_column("alerts", "pattern_type")
    op.drop_column("alerts", "threshold_high")
    op.drop_column("alerts", "category")
    op.execute("UPDATE alerts SET threshold_value = 0 WHERE threshold_value IS NULL")
    op.execute("ALTER TABLE alerts ALTER COLUMN threshold_value SET NOT NULL")
