"""add watchlist default flag and membership order

Revision ID: d4a7c1e83b20
Revises: c8e1a4b27d90
Create Date: 2026-09-24 19:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "d4a7c1e83b20"
down_revision: Union[str, Sequence[str], None] = "c8e1a4b27d90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("watchlists", sa.Column("is_default", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column("watchlists", sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False))
    op.create_index(
        "uq_watchlists_one_default",
        "watchlists",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_default"),
    )
    op.add_column("watchlist_stocks", sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False))
    op.add_column(
        "watchlist_stocks",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("watchlist_stocks", "updated_at")
    op.drop_column("watchlist_stocks", "sort_order")
    op.drop_index("uq_watchlists_one_default", table_name="watchlists")
    op.drop_column("watchlists", "sort_order")
    op.drop_column("watchlists", "is_default")
