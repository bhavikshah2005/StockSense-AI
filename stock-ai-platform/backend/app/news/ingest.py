"""Store provider articles. Page loads do not call this.

A Postgres advisory lock stops two workers from ingesting together.
The canonical URL hash stops a retry from inserting the same story twice.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.data_providers.news.base import NewsProvider, ProviderArticle
from app.models import NewsArticle, NewsArticleStock, NewsIngestRun, NewsSentiment, Stock
from app.models.enums import Importance, Sentiment
from app.news.matching import StockName, match_stocks
from app.news.sentiment import CLASSIFIER_NAME, classify

LOCK_KEY = 81411012


def ingest(db: Session, provider: NewsProvider, now: datetime | None = None) -> dict[str, int | str]:
    moment = now or datetime.now(UTC)
    locked = db.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": LOCK_KEY}).scalar()
    if not locked:
        return {"status": "skipped"}
    run = NewsIngestRun(provider=provider.name, status="running", started_at=moment, item_count=0)
    db.add(run)
    db.flush()
    try:
        if not provider.configured:
            run.status = "not_configured"
            run.finished_at = datetime.now(UTC)
            run.error_message = "No news feed is configured."
            db.commit()
            return {"status": "not_configured", "stored": 0}
        result = provider.fetch()
        stocks = [
            StockName(stock.id, stock.symbol, stock.company_name)
            for stock in db.scalars(select(Stock).where(Stock.is_active.is_(True), Stock.exchange.in_(["NSE", "BSE"]))).all()
        ]
        stored = 0
        for article in result.articles:
            if article.published_at is None:
                continue
            if _upsert(db, article, stocks, moment):
                stored += 1
        run.item_count = stored
        run.finished_at = datetime.now(UTC)
        if result.errors and stored == 0 and not result.articles:
            run.status = "error"
            run.error_message = "; ".join(result.errors)[:500]
        elif result.errors:
            run.status = "partial"
            run.error_message = "; ".join(result.errors)[:500]
        else:
            run.status = "success"
            run.error_message = None
        db.commit()
        return {"status": run.status, "stored": stored}
    except Exception as exc:
        run.status = "error"
        run.finished_at = datetime.now(UTC)
        run.error_message = type(exc).__name__
        db.commit()
        raise
    finally:
        db.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK_KEY})
        db.commit()


def _upsert(db: Session, article: ProviderArticle, stocks: list[StockName], now: datetime) -> bool:
    digest = hashlib.sha256(article.url.encode("utf-8")).hexdigest()
    row = db.scalar(select(NewsArticle).where(NewsArticle.content_hash == digest, NewsArticle.stock_id.is_(None)))
    created = row is None
    if row is None and article.provider_article_id:
        row = db.scalar(
            select(NewsArticle).where(
                NewsArticle.provider == article.provider,
                NewsArticle.provider_article_id == article.provider_article_id,
            )
        )
        created = row is None
    if row is None:
        row = NewsArticle(
            stock_id=None,
            title=article.title,
            description=article.summary,
            source=article.source,
            url=article.url,
            published_at=article.published_at,
            fetched_at=now,
            content_hash=digest,
            provider=article.provider,
            provider_article_id=article.provider_article_id,
            author=article.author,
            language=article.language,
            region="IN",
            status="active",
        )
        db.add(row)
        db.flush()
    else:
        row.title = article.title
        row.description = article.summary
        row.published_at = article.published_at or row.published_at
        row.author = article.author or row.author
        row.language = article.language or row.language
        row.updated_at = now
        db.flush()
    _links(db, row, article, stocks, now)
    _sentiment(db, row, article, now)
    return created


def _links(db: Session, row: NewsArticle, article: ProviderArticle, stocks: list[StockName], now: datetime) -> None:
    existing = set(db.scalars(select(NewsArticleStock.stock_id).where(NewsArticleStock.news_article_id == row.id)).all())
    for match in match_stocks(article.title, article.summary, stocks):
        if match.stock_id in existing or match.quality != "confirmed":
            continue
        db.add(
            NewsArticleStock(
                news_article_id=row.id,
                stock_id=match.stock_id,
                match_method=match.method,
                quality=match.quality,
                associated_at=now,
            )
        )
        existing.add(match.stock_id)


def _sentiment(db: Session, row: NewsArticle, article: ProviderArticle, now: datetime) -> None:
    reading = classify(article.title, article.summary)
    current = db.scalar(
        select(NewsSentiment).where(NewsSentiment.news_article_id == row.id, NewsSentiment.model_name == CLASSIFIER_NAME)
    )
    if current is None:
        db.add(
            NewsSentiment(
                news_article_id=row.id,
                sentiment=Sentiment(reading.label),
                sentiment_score=Decimal(reading.score),
                importance=Importance.LOW,
                impact_score=None,
                model_name=CLASSIFIER_NAME,
                analyzed_at=now,
                explanation=reading.explanation,
                input_basis=reading.input_basis,
            )
        )
        return
    current.sentiment = Sentiment(reading.label)
    current.sentiment_score = Decimal(reading.score)
    current.analyzed_at = now
    current.explanation = reading.explanation
    current.input_basis = reading.input_basis
