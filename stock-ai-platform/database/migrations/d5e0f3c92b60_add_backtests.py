"""add backtest runs, trades, and equity points

Revision ID: d5e0f3c92b60
Revises: c4d9e2b81a50
Create Date: 2026-09-25 09:40:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "d5e0f3c92b60"
down_revision: Union[str, Sequence[str], None] = "c4d9e2b81a50"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "backtest_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("stock_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("strategy_key", sa.String(length=40), nullable=False),
        sa.Column("strategy_version", sa.String(length=16), nullable=False),
        sa.Column("parameters", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("assumptions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="queued", nullable=False),
        sa.Column("requested_start", sa.Date(), nullable=False),
        sa.Column("requested_end", sa.Date(), nullable=False),
        sa.Column("actual_start", sa.Date(), nullable=True),
        sa.Column("actual_end", sa.Date(), nullable=True),
        sa.Column("initial_capital", sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column("engine_version", sa.String(length=32), nullable=False),
        sa.Column("indicator_version", sa.String(length=32), nullable=False),
        sa.Column("detector_version", sa.String(length=32), nullable=False),
        sa.Column("data_source", sa.String(length=80), nullable=False),
        sa.Column("price_basis", sa.String(length=32), nullable=False),
        sa.Column("summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("warnings", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["stock_id"], ["stocks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_backtest_runs_user_created", "backtest_runs", ["user_id", "created_at"])
    op.create_index("ix_backtest_runs_user_status", "backtest_runs", ["user_id", "status"])
    op.execute("ALTER TABLE backtest_runs ADD CONSTRAINT ck_backtest_runs_status CHECK (status IN ('queued', 'running', 'completed', 'partial', 'insufficient_data', 'failed'))")
    op.execute("ALTER TABLE backtest_runs ADD CONSTRAINT ck_backtest_runs_capital CHECK (initial_capital > 0)")
    op.execute("ALTER TABLE backtest_runs ADD CONSTRAINT ck_backtest_runs_range CHECK (requested_start < requested_end)")
    op.create_table(
        "backtest_trades",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trade_number", sa.Integer(), nullable=False),
        sa.Column("signal_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("entry_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("exit_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("entry_price", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("exit_price", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("shares", sa.Integer(), nullable=False),
        sa.Column("entry_charges", sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column("exit_charges", sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column("slippage_cost", sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column("exit_reason", sa.String(length=40), nullable=False),
        sa.Column("pnl", sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column("return_percent", sa.Numeric(precision=12, scale=6), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["backtest_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_backtest_trades_run_number", "backtest_trades", ["run_id", "trade_number"], unique=True)
    op.execute("ALTER TABLE backtest_trades ADD CONSTRAINT ck_backtest_trades_shares CHECK (shares > 0)")
    op.execute("ALTER TABLE backtest_trades ADD CONSTRAINT ck_backtest_trades_prices CHECK (entry_price > 0 AND exit_price > 0)")
    op.create_table(
        "backtest_equity_points",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("point_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("equity", sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column("drawdown_percent", sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column("cash", sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column("shares", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["backtest_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_backtest_equity_run_time", "backtest_equity_points", ["run_id", "point_at"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_backtest_equity_run_time", table_name="backtest_equity_points")
    op.drop_table("backtest_equity_points")
    op.drop_index("ix_backtest_trades_run_number", table_name="backtest_trades")
    op.drop_table("backtest_trades")
    op.drop_index("ix_backtest_runs_user_status", table_name="backtest_runs")
    op.drop_index("ix_backtest_runs_user_created", table_name="backtest_runs")
    op.drop_table("backtest_runs")
