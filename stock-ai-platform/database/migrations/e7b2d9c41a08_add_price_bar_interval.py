"""add price bar interval

Revision ID: e7b2d9c41a08
Revises: c4a8e1b27f03
Create Date: 2026-09-23 22:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e7b2d9c41a08"
down_revision: Union[str, Sequence[str], None] = "c4a8e1b27f03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "stock_prices",
        sa.Column("interval", sa.String(length=8), server_default="1d", nullable=False),
    )
    op.drop_index("ix_stock_prices_stock_id_timestamp", table_name="stock_prices")
    op.create_index(
        "ix_stock_prices_stock_interval_timestamp",
        "stock_prices",
        ["stock_id", "interval", "timestamp"],
        unique=True,
    )
    op.create_check_constraint(
        "ck_stock_prices_prices_nonnegative",
        "stock_prices",
        "open >= 0 AND high >= 0 AND low >= 0 AND close >= 0",
    )
    op.create_check_constraint(
        "ck_stock_prices_adjusted_close_nonnegative",
        "stock_prices",
        "adjusted_close IS NULL OR adjusted_close >= 0",
    )
    op.create_check_constraint(
        "ck_stock_prices_interval_known",
        "stock_prices",
        "interval IN ('1d', '1h', '15m')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_stock_prices_interval_known", "stock_prices", type_="check")
    op.drop_constraint("ck_stock_prices_adjusted_close_nonnegative", "stock_prices", type_="check")
    op.drop_constraint("ck_stock_prices_prices_nonnegative", "stock_prices", type_="check")
    op.drop_index("ix_stock_prices_stock_interval_timestamp", table_name="stock_prices")
    op.create_index(
        "ix_stock_prices_stock_id_timestamp",
        "stock_prices",
        ["stock_id", "timestamp"],
        unique=True,
    )
    op.drop_column("stock_prices", "interval")
