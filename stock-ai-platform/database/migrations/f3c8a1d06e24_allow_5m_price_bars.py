"""allow 5m price bars

Revision ID: f3c8a1d06e24
Revises: e7b2d9c41a08
Create Date: 2026-09-23 23:15:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "f3c8a1d06e24"
down_revision: Union[str, Sequence[str], None] = "e7b2d9c41a08"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ck_stock_prices_interval_known", "stock_prices", type_="check")
    op.create_check_constraint(
        "ck_stock_prices_interval_known",
        "stock_prices",
        "interval IN ('1d', '1h', '15m', '5m')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_stock_prices_interval_known", "stock_prices", type_="check")
    op.create_check_constraint(
        "ck_stock_prices_interval_known",
        "stock_prices",
        "interval IN ('1d', '1h', '15m')",
    )
