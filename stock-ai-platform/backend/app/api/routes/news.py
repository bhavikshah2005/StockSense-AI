from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import NewsArticle, User
from app.news.sentiment import CLASSIFIER_NAME
from app.schemas.news import (
    NewsCard,
    NewsFacets,
    NewsListResponse,
    NewsStatusResponse,
    NewsStockLink,
    SentimentDetail,
)
from app.services.news_service import METHODOLOGY, facets, feed_status, get_article, links_for, list_news, sentiment_for

router = APIRouter(prefix="/api/news", tags=["news"])

_LABELS = {"positive", "negative", "neutral", "uncertain", "unavailable"}


def _cards(db: Session, rows: list[NewsArticle]) -> list[NewsCard]:
    ids = [row.id for row in rows]
    links = links_for(db, ids)
    readings = sentiment_for(db, ids)
    cards: list[NewsCard] = []
    for row in rows:
        reading = readings.get(row.id)
        cards.append(
            NewsCard(
                id=row.id,
                title=row.title,
                summary=row.description,
                source=row.source,
                url=row.url,
                author=row.author,
                published_at=row.published_at,
                ingested_at=row.fetched_at,
                language=row.language,
                sentiment=reading.sentiment.value if reading is not None else None,
                sentiment_explanation=reading.explanation if reading is not None else None,
                stocks=[
                    NewsStockLink(
                        stock_id=stock.id,
                        symbol=stock.symbol,
                        exchange=stock.exchange,
                        company_name=stock.company_name,
                        match_method=link.match_method,
                    )
                    for link, stock in links.get(row.id, [])
                ],
            )
        )
    return cards


@router.get("/status", response_model=NewsStatusResponse, summary="News feed freshness")
def status(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> NewsStatusResponse:
    del user
    return NewsStatusResponse.model_validate(feed_status(db))


@router.get("/facets", response_model=NewsFacets, summary="Sources and sectors for filters")
def news_facets(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> NewsFacets:
    del user
    sources, sectors = facets(db)
    return NewsFacets(sources=sources, sectors=sectors)


@router.get("", response_model=NewsListResponse, summary="Recent Indian market news")
def news(
    stock_id: UUID | None = None,
    sector: str | None = Query(default=None, max_length=128),
    source: str | None = Query(default=None, max_length=255),
    sentiment: str | None = None,
    published_from: str | None = None,
    published_to: str | None = None,
    window_days: int | None = Query(default=None, ge=1, le=90),
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NewsListResponse:
    del user
    if sentiment is not None and sentiment not in _LABELS:
        raise HTTPException(status_code=422, detail="That sentiment filter is not supported")
    start = _time(published_from)
    end = _time(published_to)
    rows, total = list_news(
        db,
        stock_id=stock_id,
        sector=sector,
        source=source,
        sentiment=sentiment,
        published_from=start,
        published_to=end,
        window_days=window_days,
        limit=limit,
        offset=offset,
    )
    return NewsListResponse(results=_cards(db, rows), total=total, limit=limit, offset=offset)


@router.get("/{article_id}", response_model=NewsCard, summary="One stored article")
def article(
    article_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NewsCard:
    del user
    row = get_article(db, article_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Article not found")
    return _cards(db, [row])[0]


@router.get("/{article_id}/sentiment", response_model=SentimentDetail, summary="Classifier reading for one article")
def article_sentiment(
    article_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SentimentDetail:
    del user
    row = get_article(db, article_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Article not found")
    reading = sentiment_for(db, [row.id]).get(row.id)
    if reading is None:
        return SentimentDetail(
            classifier=CLASSIFIER_NAME,
            label=None,
            explanation=None,
            input_basis=None,
            analyzed_at=None,
            available=False,
            methodology=METHODOLOGY,
        )
    label = reading.sentiment.value if hasattr(reading.sentiment, "value") else str(reading.sentiment)
    return SentimentDetail(
        classifier=CLASSIFIER_NAME,
        label=label,
        explanation=reading.explanation,
        input_basis=reading.input_basis,
        analyzed_at=reading.analyzed_at,
        available=True,
        methodology=METHODOLOGY,
    )


def _time(value: str | None):
    if value is None or value == "":
        return None
    from datetime import datetime

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="That time filter is not a valid timestamp") from exc
    return parsed
