"""add stock isin

Revision ID: c4a8e1b27f03
Revises: b7e1c4a92d10
Create Date: 2026-09-23 21:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4a8e1b27f03"
down_revision: Union[str, Sequence[str], None] = "b7e1c4a92d10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("stocks", sa.Column("isin", sa.String(length=12), nullable=True))
    op.create_check_constraint("ck_stocks_isin_length", "stocks", "isin IS NULL OR char_length(isin) = 12")
    op.create_index("ix_stocks_isin", "stocks", ["isin"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_stocks_isin", table_name="stocks")
    op.drop_constraint("ck_stocks_isin_length", "stocks", type_="check")
    op.drop_column("stocks", "isin")
