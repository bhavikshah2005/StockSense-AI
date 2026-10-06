"""Read stored news. This module does not call a provider."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.data_providers.news import get_news_provider
from app.models import NewsArticle, NewsArticleStock, NewsIngestRun, NewsSentiment, Stock
from app.news.sentiment import CLASSIFIER_NAME

METHODOLOGY = (
    "Sentiment uses a fixed word list, lexicon-1, on the headline and a short excerpt. "
    "Mixed or very short text is uncertain. A label is not a forecast and is not a buy, hold, or sell instruction."
)


def list_news(
    db: Session,
    *,
    stock_id: UUID | None,
    sector: str | None,
    source: str | None,
    sentiment: str | None,
    published_from: datetime | None,
    published_to: datetime | None,
    window_days: int | None,
    limit: int,
    offset: int,
) -> tuple[list[NewsArticle], int]:
    statement = select(NewsArticle).where(NewsArticle.status == "active", NewsArticle.region == "IN")
    if published_from is None and published_to is None:
        days = window_days or settings.news_default_window_days
        published_from = datetime.now(UTC) - timedelta(days=days)
    if published_from is not None:
        statement = statement.where(NewsArticle.published_at >= published_from)
    if published_to is not None:
        statement = statement.where(NewsArticle.published_at <= published_to)
    if source:
        statement = statement.where(NewsArticle.source == source)
    if stock_id is not None:
        statement = statement.where(
            NewsArticle.id.in_(
                select(NewsArticleStock.news_article_id).where(
                    NewsArticleStock.stock_id == stock_id,
                    NewsArticleStock.quality == "confirmed",
                )
            )
        )
    if sector:
        statement = statement.where(
            NewsArticle.id.in_(
                select(NewsArticleStock.news_article_id)
                .join(Stock, Stock.id == NewsArticleStock.stock_id)
                .where(Stock.sector == sector, NewsArticleStock.quality == "confirmed")
            )
        )
    if sentiment == "unavailable":
        statement = statement.where(
            ~NewsArticle.id.in_(select(NewsSentiment.news_article_id).where(NewsSentiment.model_name == CLASSIFIER_NAME))
        )
    elif sentiment:
        statement = statement.where(
            NewsArticle.id.in_(
                select(NewsSentiment.news_article_id).where(
                    NewsSentiment.model_name == CLASSIFIER_NAME,
                    NewsSentiment.sentiment == sentiment,
                )
            )
        )
    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    rows = list(
        db.scalars(statement.order_by(NewsArticle.published_at.desc(), NewsArticle.id.desc()).limit(limit).offset(offset)).all()
    )
    return rows, int(total)


def get_article(db: Session, article_id: UUID) -> NewsArticle | None:
    return db.scalar(select(NewsArticle).where(NewsArticle.id == article_id, NewsArticle.status == "active"))


def links_for(db: Session, article_ids: list[UUID]) -> dict[UUID, list[tuple[NewsArticleStock, Stock]]]:
    if not article_ids:
        return {}
    rows = db.execute(
        select(NewsArticleStock, Stock)
        .join(Stock, Stock.id == NewsArticleStock.stock_id)
        .where(NewsArticleStock.news_article_id.in_(article_ids), NewsArticleStock.quality == "confirmed")
    ).all()
    grouped: dict[UUID, list[tuple[NewsArticleStock, Stock]]] = {}
    for link, stock in rows:
        grouped.setdefault(link.news_article_id, []).append((link, stock))
    return grouped


def sentiment_for(db: Session, article_ids: list[UUID]) -> dict[UUID, NewsSentiment]:
    if not article_ids:
        return {}
    rows = db.scalars(
        select(NewsSentiment).where(NewsSentiment.news_article_id.in_(article_ids), NewsSentiment.model_name == CLASSIFIER_NAME)
    ).all()
    return {row.news_article_id: row for row in rows}


def facets(db: Session) -> tuple[list[str], list[str]]:
    sources = list(
        db.scalars(select(NewsArticle.source).where(NewsArticle.status == "active").distinct().order_by(NewsArticle.source)).all()
    )
    sectors = list(
        db.scalars(select(Stock.sector).where(Stock.sector.is_not(None), Stock.is_active.is_(True)).distinct().order_by(Stock.sector)).all()
    )
    return sources, [sector for sector in sectors if sector]


def feed_status(db: Session, now: datetime | None = None) -> dict[str, object]:
    moment = now or datetime.now(UTC)
    provider = get_news_provider()
    latest = db.scalar(select(NewsIngestRun).order_by(NewsIngestRun.started_at.desc()).limit(1))
    success = db.scalar(
        select(NewsIngestRun)
        .where(NewsIngestRun.status.in_(["success", "partial"]))
        .order_by(NewsIngestRun.finished_at.desc())
        .limit(1)
    )
    last_success = success.finished_at if success else None
    stale = last_success is None or last_success < moment - timedelta(seconds=settings.news_ingest_interval_seconds * 2)
    if not provider.configured:
        message = "News feeds are not configured. Add NEWS_PROVIDER=rss and NEWS_RSS_FEEDS on the server."
    elif stale:
        message = "No recent ingest has completed. The feed is not live."
    else:
        message = "Headlines come from the last completed ingest. This is not a live feed."
    return {
        "configured": provider.configured,
        "provider": provider.name,
        "last_success_at": last_success,
        "last_status": latest.status if latest else None,
        "last_error": latest.error_message if latest and latest.status in {"error", "partial", "not_configured"} else None,
        "stale": stale or not provider.configured,
        "message": message,
    }
