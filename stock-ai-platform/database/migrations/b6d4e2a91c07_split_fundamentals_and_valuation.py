"""split reported fundamentals from valuation snapshots

Revision ID: b6d4e2a91c07
Revises: f3c8a1d06e24
Create Date: 2026-09-23 23:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b6d4e2a91c07"
down_revision: Union[str, Sequence[str], None] = "f3c8a1d06e24"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("fundamentals", sa.Column("fiscal_period_type", sa.String(length=16), server_default="annual", nullable=False))
    op.add_column("fundamentals", sa.Column("filing_date", sa.Date(), nullable=True))
    op.add_column("fundamentals", sa.Column("currency", sa.String(length=3), server_default="INR", nullable=False))
    op.add_column("fundamentals", sa.Column("ebitda", sa.Numeric(precision=20, scale=2), nullable=True))
    op.add_column("fundamentals", sa.Column("ebitda_growth", sa.Numeric(precision=18, scale=6), nullable=True))
    op.add_column("fundamentals", sa.Column("operating_profit", sa.Numeric(precision=20, scale=2), nullable=True))
    op.add_column("fundamentals", sa.Column("eps_growth", sa.Numeric(precision=18, scale=6), nullable=True))
    op.add_column("fundamentals", sa.Column("book_value_per_share", sa.Numeric(precision=18, scale=4), nullable=True))
    op.add_column("fundamentals", sa.Column("operating_cash_flow", sa.Numeric(precision=20, scale=2), nullable=True))
    op.add_column("fundamentals", sa.Column("source", sa.String(length=64), server_default="unknown", nullable=False))
    op.add_column("fundamentals", sa.Column("provider_retrieved_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint(
        "ck_fundamentals_fiscal_period_type",
        "fundamentals",
        "fiscal_period_type IN ('annual', 'quarterly')",
    )
    op.create_check_constraint("ck_fundamentals_currency_code", "fundamentals", "char_length(currency) = 3")
    op.create_check_constraint("ck_fundamentals_currency_upper", "fundamentals", "currency = upper(currency)")
    op.create_table(
        "valuation_snapshots",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("stock_id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("market_price", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("market_cap", sa.Numeric(precision=20, scale=2), nullable=True),
        sa.Column("enterprise_value", sa.Numeric(precision=20, scale=2), nullable=True),
        sa.Column("pe_ratio", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("pb_ratio", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("peg_ratio", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("ev_to_ebitda", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("ev_to_sales", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("dividend_yield", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("provider_retrieved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("char_length(currency) = 3", name="ck_valuation_snapshots_currency_code"),
        sa.CheckConstraint("currency = upper(currency)", name="ck_valuation_snapshots_currency_upper"),
        sa.ForeignKeyConstraint(["stock_id"], ["stocks.id"], name="fk_valuation_snapshots_stock_id_stocks", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_valuation_snapshots"),
        sa.UniqueConstraint("stock_id", "snapshot_at", "source", name="uq_valuation_snapshots_stock_time_source"),
    )
    op.create_index(
        "ix_valuation_snapshots_stock_id_snapshot_at",
        "valuation_snapshots",
        ["stock_id", "snapshot_at"],
        unique=False,
    )
    op.execute(
        """
        INSERT INTO valuation_snapshots (
            stock_id, snapshot_at, pe_ratio, pb_ratio, peg_ratio, ev_to_ebitda, ev_to_sales,
            dividend_yield, currency, source, provider_retrieved_at
        )
        SELECT
            stock_id,
            (report_date::timestamp AT TIME ZONE 'Asia/Kolkata'),
            pe_ratio, pb_ratio, peg_ratio, ev_ebitda, ev_sales, dividend_yield,
            'INR', 'migrated', updated_at
        FROM fundamentals
        WHERE pe_ratio IS NOT NULL
           OR pb_ratio IS NOT NULL
           OR peg_ratio IS NOT NULL
           OR ev_ebitda IS NOT NULL
           OR ev_sales IS NOT NULL
           OR dividend_yield IS NOT NULL
        """
    )
    op.drop_constraint("uq_fundamentals_stock_report_period", "fundamentals", type_="unique")
    op.create_unique_constraint(
        "uq_fundamentals_stock_report_period_source",
        "fundamentals",
        ["stock_id", "report_date", "fiscal_period", "source"],
    )
    for column in ("pe_ratio", "pb_ratio", "peg_ratio", "ev_ebitda", "ev_sales", "dividend_yield"):
        op.drop_column("fundamentals", column)
    op.add_column("sector_benchmarks", sa.Column("currency", sa.String(length=3), nullable=True))
    op.add_column("sector_benchmarks", sa.Column("source", sa.String(length=64), nullable=True))
    op.add_column("sector_benchmarks", sa.Column("methodology", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("sector_benchmarks", "methodology")
    op.drop_column("sector_benchmarks", "source")
    op.drop_column("sector_benchmarks", "currency")
    op.add_column("fundamentals", sa.Column("dividend_yield", sa.Numeric(precision=18, scale=6), nullable=True))
    op.add_column("fundamentals", sa.Column("ev_sales", sa.Numeric(precision=18, scale=6), nullable=True))
    op.add_column("fundamentals", sa.Column("ev_ebitda", sa.Numeric(precision=18, scale=6), nullable=True))
    op.add_column("fundamentals", sa.Column("peg_ratio", sa.Numeric(precision=18, scale=6), nullable=True))
    op.add_column("fundamentals", sa.Column("pb_ratio", sa.Numeric(precision=18, scale=6), nullable=True))
    op.add_column("fundamentals", sa.Column("pe_ratio", sa.Numeric(precision=18, scale=6), nullable=True))
    op.drop_constraint("uq_fundamentals_stock_report_period_source", "fundamentals", type_="unique")
    op.create_unique_constraint(
        "uq_fundamentals_stock_report_period",
        "fundamentals",
        ["stock_id", "report_date", "fiscal_period"],
    )
    op.drop_index("ix_valuation_snapshots_stock_id_snapshot_at", table_name="valuation_snapshots")
    op.drop_table("valuation_snapshots")
    op.drop_constraint("ck_fundamentals_currency_upper", "fundamentals", type_="check")
    op.drop_constraint("ck_fundamentals_currency_code", "fundamentals", type_="check")
    op.drop_constraint("ck_fundamentals_fiscal_period_type", "fundamentals", type_="check")
    for column in (
        "provider_retrieved_at",
        "source",
        "operating_cash_flow",
        "book_value_per_share",
        "eps_growth",
        "operating_profit",
        "ebitda_growth",
        "ebitda",
        "currency",
        "filing_date",
        "fiscal_period_type",
    ):
        op.drop_column("fundamentals", column)
