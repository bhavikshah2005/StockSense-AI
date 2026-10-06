"""Stored headlines, stock links, and lexicon sentiment.

`content_hash` is the canonical URL hash. The same URL is stored once.
`stock_id` remains for older rows. New links live in `news_article_stocks`.
`fetched_at` is when this app stored the row, not when the publisher wrote it.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Index, Numeric, String, Text, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import IMPORTANCE, SENTIMENT, Importance, Sentiment
from app.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin, uuid_fk

if TYPE_CHECKING:
    from app.models.stock import Stock


class NewsArticle(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "news_articles"
    __table_args__ = (
        UniqueConstraint(
            "stock_id",
            "content_hash",
            name="uq_news_articles_stock_id_content_hash",
            postgresql_nulls_not_distinct=True,
        ),
        Index("ix_news_articles_stock_id_published_at", "stock_id", "published_at"),
        Index("ix_news_articles_published_at", "published_at"),
        Index("ix_news_articles_source_published_at", "source", "published_at"),
        Index("ix_news_articles_status_published_at", "status", "published_at"),
        CheckConstraint(
            "status IN ('active', 'withdrawn', 'unavailable')",
            name="ck_news_articles_status",
        ),
    )

    stock_id: Mapped[uuid.UUID | None] = uuid_fk("stocks.id", ondelete="SET NULL", nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False, default="legacy", server_default=text("'legacy'"))
    provider_article_id: Mapped[str | None] = mapped_column(String(255))
    author: Mapped[str | None] = mapped_column(String(255))
    language: Mapped[str | None] = mapped_column(String(16))
    region: Mapped[str] = mapped_column(String(8), nullable=False, default="IN", server_default=text("'IN'"))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active", server_default=text("'active'"))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    stock: Mapped[Stock | None] = relationship(back_populates="news_articles")
    sentiments: Mapped[list[NewsSentiment]] = relationship(
        back_populates="article",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    stock_links: Mapped[list[NewsArticleStock]] = relationship(
        back_populates="article",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class NewsArticleStock(Base, UUIDPrimaryKeyMixin):
    """One article linked to one stock master row."""

    __tablename__ = "news_article_stocks"
    __table_args__ = (
        UniqueConstraint("news_article_id", "stock_id", name="uq_news_article_stocks_article_stock"),
        Index("ix_news_article_stocks_stock_id", "stock_id"),
        CheckConstraint(
            "match_method IN ('symbol', 'company_name')",
            name="ck_news_article_stocks_method",
        ),
        CheckConstraint(
            "quality IN ('confirmed', 'uncertain')",
            name="ck_news_article_stocks_quality",
        ),
    )

    news_article_id: Mapped[uuid.UUID] = uuid_fk("news_articles.id", ondelete="CASCADE")
    stock_id: Mapped[uuid.UUID] = uuid_fk("stocks.id", ondelete="CASCADE")
    match_method: Mapped[str] = mapped_column(String(32), nullable=False)
    quality: Mapped[str] = mapped_column(String(16), nullable=False)
    associated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    article: Mapped[NewsArticle] = relationship(back_populates="stock_links")
    stock: Mapped[Stock] = relationship(back_populates="news_links")


class NewsSentiment(Base, UUIDPrimaryKeyMixin):
    """One classifier reading of an article.

    `sentiment_score` is a direction flag for the lexicon classifier, not a probability
    and not a forecast of the share price.
    """

    __tablename__ = "news_sentiment"
    __table_args__ = (
        UniqueConstraint(
            "news_article_id",
            "model_name",
            name="uq_news_sentiment_article_model",
        ),
        Index("ix_news_sentiment_news_article_id", "news_article_id"),
        Index("ix_news_sentiment_label", "sentiment"),
    )

    news_article_id: Mapped[uuid.UUID] = uuid_fk("news_articles.id", ondelete="CASCADE")
    sentiment: Mapped[Sentiment] = mapped_column(SENTIMENT, nullable=False)
    sentiment_score: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    importance: Mapped[Importance] = mapped_column(IMPORTANCE, nullable=False)
    impact_score: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text)
    input_basis: Mapped[str | None] = mapped_column(String(32))

    article: Mapped[NewsArticle] = relationship(back_populates="sentiments")


class NewsIngestRun(Base, UUIDPrimaryKeyMixin):
    """One provider fetch. Errors are short and do not include credentials."""

    __tablename__ = "news_ingest_runs"
    __table_args__ = (Index("ix_news_ingest_runs_started_at", "started_at"),)

    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    item_count: Mapped[int] = mapped_column(nullable=False, default=0, server_default=text("0"))
    error_message: Mapped[str | None] = mapped_column(Text)
