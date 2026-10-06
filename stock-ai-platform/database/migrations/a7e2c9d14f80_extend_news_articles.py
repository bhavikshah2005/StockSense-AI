"""extend news articles with providers, stock links, and ingest runs

Revision ID: a7e2c9d14f80
Revises: f8c3b2a91e40
Create Date: 2026-09-24 23:55:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "a7e2c9d14f80"
down_revision: Union[str, Sequence[str], None] = "f8c3b2a91e40"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE sentiment_label ADD VALUE IF NOT EXISTS 'uncertain'")
    op.add_column("news_articles", sa.Column("provider", sa.String(length=64), server_default="legacy", nullable=False))
    op.add_column("news_articles", sa.Column("provider_article_id", sa.String(length=255), nullable=True))
    op.add_column("news_articles", sa.Column("author", sa.String(length=255), nullable=True))
    op.add_column("news_articles", sa.Column("language", sa.String(length=16), nullable=True))
    op.add_column("news_articles", sa.Column("region", sa.String(length=8), server_default="IN", nullable=False))
    op.add_column("news_articles", sa.Column("status", sa.String(length=16), server_default="active", nullable=False))
    op.add_column("news_articles", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
    op.execute(
        "ALTER TABLE news_articles ADD CONSTRAINT ck_news_articles_status CHECK (status IN ('active', 'withdrawn', 'unavailable'))"
    )
    op.create_index("ix_news_articles_source_published_at", "news_articles", ["source", "published_at"])
    op.create_index("ix_news_articles_status_published_at", "news_articles", ["status", "published_at"])
    op.create_index(
        "uq_news_articles_provider_article",
        "news_articles",
        ["provider", "provider_article_id"],
        unique=True,
        postgresql_where=sa.text("provider_article_id IS NOT NULL"),
    )
    op.add_column("news_sentiment", sa.Column("explanation", sa.Text(), nullable=True))
    op.add_column("news_sentiment", sa.Column("input_basis", sa.String(length=32), nullable=True))
    op.create_index("ix_news_sentiment_label", "news_sentiment", ["sentiment"])
    op.create_table(
        "news_article_stocks",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("news_article_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("stock_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("match_method", sa.String(length=32), nullable=False),
        sa.Column("quality", sa.String(length=16), nullable=False),
        sa.Column("associated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["news_article_id"], ["news_articles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["stock_id"], ["stocks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("news_article_id", "stock_id", name="uq_news_article_stocks_article_stock"),
        sa.CheckConstraint("match_method IN ('symbol', 'company_name')", name="ck_news_article_stocks_method"),
        sa.CheckConstraint("quality IN ('confirmed', 'uncertain')", name="ck_news_article_stocks_quality"),
    )
    op.create_index("ix_news_article_stocks_stock_id", "news_article_stocks", ["stock_id"])
    op.create_table(
        "news_ingest_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("item_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_news_ingest_runs_started_at", "news_ingest_runs", ["started_at"])


def downgrade() -> None:
    op.drop_index("ix_news_ingest_runs_started_at", table_name="news_ingest_runs")
    op.drop_table("news_ingest_runs")
    op.drop_index("ix_news_article_stocks_stock_id", table_name="news_article_stocks")
    op.drop_table("news_article_stocks")
    op.drop_index("ix_news_sentiment_label", table_name="news_sentiment")
    op.drop_column("news_sentiment", "input_basis")
    op.drop_column("news_sentiment", "explanation")
    op.execute("DROP INDEX IF EXISTS uq_news_articles_provider_article")
    op.drop_index("ix_news_articles_status_published_at", table_name="news_articles")
    op.drop_index("ix_news_articles_source_published_at", table_name="news_articles")
    op.execute("ALTER TABLE news_articles DROP CONSTRAINT IF EXISTS ck_news_articles_status")
    op.drop_column("news_articles", "updated_at")
    op.drop_column("news_articles", "status")
    op.drop_column("news_articles", "region")
    op.drop_column("news_articles", "language")
    op.drop_column("news_articles", "author")
    op.drop_column("news_articles", "provider_article_id")
    op.drop_column("news_articles", "provider")
