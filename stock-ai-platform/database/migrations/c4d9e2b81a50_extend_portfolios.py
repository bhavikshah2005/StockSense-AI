"""add portfolio transactions, cash movements, and risk settings

Revision ID: c4d9e2b81a50
Revises: b3c8e1a94d20
Create Date: 2026-09-25 00:40:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "c4d9e2b81a50"
down_revision: Union[str, Sequence[str], None] = "b3c8e1a94d20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("portfolios", sa.Column("currency", sa.String(length=3), server_default="INR", nullable=False))
    op.add_column("portfolios", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("ALTER TABLE portfolios ADD CONSTRAINT ck_portfolios_currency_inr CHECK (currency = 'INR')")
    op.execute("ALTER TABLE portfolios ADD CONSTRAINT ck_portfolios_available_cash_nonnegative CHECK (available_cash >= 0)")
    op.add_column(
        "portfolio_holdings",
        sa.Column("cost_basis", sa.Numeric(precision=20, scale=2), server_default="0", nullable=False),
    )
    op.execute("UPDATE portfolio_holdings SET cost_basis = round(quantity * average_buy_price, 2)")
    op.execute("ALTER TABLE portfolio_holdings ADD CONSTRAINT ck_portfolio_holdings_cost_basis_nonnegative CHECK (cost_basis >= 0)")
    op.create_table(
        "portfolio_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("portfolio_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("stock_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("price", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("charges", sa.Numeric(precision=20, scale=2), server_default=sa.text("0"), nullable=False),
        sa.Column("traded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["stock_id"], ["stocks.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("side IN ('buy', 'sell')", name="ck_portfolio_transactions_side"),
        sa.CheckConstraint("quantity > 0 AND quantity = trunc(quantity)", name="ck_portfolio_transactions_whole_shares"),
        sa.CheckConstraint("price > 0", name="ck_portfolio_transactions_price"),
        sa.CheckConstraint("charges >= 0", name="ck_portfolio_transactions_charges"),
    )
    op.create_index("ix_portfolio_transactions_portfolio_traded", "portfolio_transactions", ["portfolio_id", "traded_at"])
    op.create_index("ix_portfolio_transactions_stock_id", "portfolio_transactions", ["stock_id"])
    op.create_table(
        "portfolio_cash_movements",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("portfolio_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("amount", sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("kind IN ('deposit', 'withdrawal')", name="ck_portfolio_cash_kind"),
        sa.CheckConstraint("amount > 0", name="ck_portfolio_cash_amount"),
    )
    op.create_index("ix_portfolio_cash_movements_portfolio_occurred", "portfolio_cash_movements", ["portfolio_id", "occurred_at"])
    op.create_table(
        "user_risk_settings",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("capital_inr", sa.Numeric(precision=20, scale=2), nullable=True),
        sa.Column("max_risk_inr", sa.Numeric(precision=20, scale=2), nullable=True),
        sa.Column("max_risk_percent", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("max_allocation_percent", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("max_shares", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
        sa.CheckConstraint("capital_inr IS NULL OR capital_inr >= 0", name="ck_user_risk_capital"),
        sa.CheckConstraint("max_risk_inr IS NULL OR max_risk_inr > 0", name="ck_user_risk_inr"),
        sa.CheckConstraint("max_risk_percent IS NULL OR (max_risk_percent > 0 AND max_risk_percent <= 100)", name="ck_user_risk_percent"),
        sa.CheckConstraint(
            "max_allocation_percent IS NULL OR (max_allocation_percent > 0 AND max_allocation_percent <= 100)",
            name="ck_user_risk_allocation",
        ),
        sa.CheckConstraint("max_shares IS NULL OR max_shares >= 1", name="ck_user_risk_shares"),
    )


def downgrade() -> None:
    op.drop_table("user_risk_settings")
    op.drop_index("ix_portfolio_cash_movements_portfolio_occurred", table_name="portfolio_cash_movements")
    op.drop_table("portfolio_cash_movements")
    op.drop_index("ix_portfolio_transactions_stock_id", table_name="portfolio_transactions")
    op.drop_index("ix_portfolio_transactions_portfolio_traded", table_name="portfolio_transactions")
    op.drop_table("portfolio_transactions")
    op.execute("ALTER TABLE portfolio_holdings DROP CONSTRAINT IF EXISTS ck_portfolio_holdings_cost_basis_nonnegative")
    op.drop_column("portfolio_holdings", "cost_basis")
    op.execute("ALTER TABLE portfolios DROP CONSTRAINT IF EXISTS ck_portfolios_available_cash_nonnegative")
    op.execute("ALTER TABLE portfolios DROP CONSTRAINT IF EXISTS ck_portfolios_currency_inr")
    op.drop_column("portfolios", "archived_at")
    op.drop_column("portfolios", "currency")
