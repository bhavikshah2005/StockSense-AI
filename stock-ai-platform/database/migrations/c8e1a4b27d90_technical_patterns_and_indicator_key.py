"""add pattern results and indicator identity columns

Revision ID: c8e1a4b27d90
Revises: b6d4e2a91c07
Create Date: 2026-09-24 18:40:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "c8e1a4b27d90"
down_revision: Union[str, Sequence[str], None] = "b6d4e2a91c07"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("technical_indicators", sa.Column("interval", sa.String(length=8), server_default="1d", nullable=False))
    op.add_column(
        "technical_indicators",
        sa.Column("calculation_version", sa.String(length=32), server_default="indicators-1", nullable=False),
    )
    op.add_column(
        "technical_indicators",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.drop_index("ix_technical_indicators_stock_id_timestamp", table_name="technical_indicators")
    op.create_index(
        "ix_technical_indicators_identity",
        "technical_indicators",
        ["stock_id", "interval", "timestamp", "calculation_version"],
        unique=True,
    )
    op.create_table(
        "technical_patterns",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("stock_id", sa.Uuid(), nullable=False),
        sa.Column("pattern_type", sa.String(length=64), nullable=False),
        sa.Column("direction", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("interval", sa.String(length=8), nullable=False),
        sa.Column("start_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("key_levels", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("pivot_evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("evidence_summary", sa.String(length=2000), nullable=False),
        sa.Column("detector_version", sa.String(length=32), nullable=False),
        sa.Column("source_price_as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('developing', 'confirmed', 'invalidated', 'completed', 'uncertain', 'insufficient_data')",
            name="ck_technical_patterns_status",
        ),
        sa.CheckConstraint("interval IN ('1d', '1h', '15m', '5m')", name="ck_technical_patterns_interval"),
        sa.ForeignKeyConstraint(["stock_id"], ["stocks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_technical_patterns_identity",
        "technical_patterns",
        ["stock_id", "interval", "pattern_type", "start_timestamp", "detector_version"],
        unique=True,
    )
    op.create_index("ix_technical_patterns_stock_id_status", "technical_patterns", ["stock_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_technical_patterns_stock_id_status", table_name="technical_patterns")
    op.drop_index("uq_technical_patterns_identity", table_name="technical_patterns")
    op.drop_table("technical_patterns")
    op.drop_index("ix_technical_indicators_identity", table_name="technical_indicators")
    op.create_index(
        "ix_technical_indicators_stock_id_timestamp",
        "technical_indicators",
        ["stock_id", "timestamp"],
        unique=True,
    )
    op.drop_column("technical_indicators", "updated_at")
    op.drop_column("technical_indicators", "calculation_version")
    op.drop_column("technical_indicators", "interval")
