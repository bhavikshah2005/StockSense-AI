"""Collect stored research inputs and optionally ask a configured model to explain them.

The model does not calculate indicators, ratios, patterns, or the coverage report.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.evidence import pack_evidence
from app.ai.explain import PROMPT_VERSION, ExplanationRejected, validate_explanation
from app.ai.provider import AiError, Explainer, get_explainer
from app.ai.scoring import SCORING_VERSION, score_evidence
from app.core.config import settings
from app.core.rate_limit import RateLimiter, get_rate_limiter
from app.metrics.service import evaluate_stock
from app.models import ResearchAnalysis, Stock, User
from app.services.news_service import list_news, sentiment_for

logger = logging.getLogger(__name__)

METHODOLOGY = {
    "prompt_version": PROMPT_VERSION,
    "scoring_version": SCORING_VERSION,
    "scoring_note": (
        "coverage-1 lists fresh fundamental comparisons, the existing technical rubric category, "
        "and stored news-sentiment counts. It does not assign a numeric stock score, a probability, "
        "or a buy, hold, or sell label. Missing inputs stay insufficient."
    ),
    "ai_note": (
        "When AI_PROVIDER=openai and AI_API_KEY and AI_MODEL are set, the model may only explain the stored evidence. "
        "Otherwise the status is ai_unavailable and no narrative is invented."
    ),
}


class ResearchError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def request_analysis(
    db: Session,
    user: User,
    stock_id: UUID,
    *,
    refresh: bool,
    explainer: Explainer | None = None,
    limiter: RateLimiter | None = None,
    evidence: dict[str, object] | None = None,
) -> ResearchAnalysis:
    stock = db.get(Stock, stock_id)
    if stock is None or not stock.is_active:
        raise ResearchError("not_found")
    model = explainer or get_explainer()
    pack = evidence or collect_evidence(db, user, stock)
    digest = str(pack["input_hash"])
    if not refresh and settings.ai_reuse_minutes > 0:
        reused = _reusable(db, user.id, stock.id, digest)
        if reused is not None:
            return reused
    budget = limiter or get_rate_limiter()
    if not budget.hit(f"ai:{user.id}", settings.ai_runs_per_hour, 3600):
        raise ResearchError("quota")
    score = score_evidence(pack)
    explanation = None
    error = None
    status = _status_without_model(score)
    if model.configured:
        try:
            raw = model.explain(pack)
            explanation = validate_explanation(raw, pack).model_dump()
            status = "complete" if score["aggregate"] == "described" else "partial"
        except ExplanationRejected as exc:
            error = exc.reason
            status = "partial"
            logger.info("research explanation rejected reason=%s", exc.reason)
        except AiError as exc:
            error = exc.code
            status = "ai_unavailable" if exc.code == "ai_unavailable" else "partial"
            logger.info("research provider failed code=%s", exc.code)
    else:
        status = "ai_unavailable"
        error = "ai_unavailable"
    row = ResearchAnalysis(
        user_id=user.id,
        stock_id=stock.id,
        status=status,
        analysis_timestamp=datetime.now(UTC),
        input_hash=digest,
        evidence=pack,
        explanation=explanation,
        score=score,
        provider=model.name,
        model_name=model.model,
        prompt_version=PROMPT_VERSION,
        scoring_version=SCORING_VERSION,
        error_message=error,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def latest_analysis(db: Session, user: User, stock_id: UUID) -> ResearchAnalysis | None:
    return db.scalar(
        select(ResearchAnalysis)
        .where(ResearchAnalysis.user_id == user.id, ResearchAnalysis.stock_id == stock_id)
        .order_by(ResearchAnalysis.created_at.desc())
        .limit(1)
    )


def get_analysis(db: Session, user: User, analysis_id: UUID) -> ResearchAnalysis | None:
    return db.scalar(select(ResearchAnalysis).where(ResearchAnalysis.id == analysis_id, ResearchAnalysis.user_id == user.id))


def list_analyses(db: Session, user: User, *, stock_id: UUID | None, limit: int, offset: int) -> tuple[list[ResearchAnalysis], int]:
    statement = select(ResearchAnalysis).where(ResearchAnalysis.user_id == user.id)
    if stock_id is not None:
        statement = statement.where(ResearchAnalysis.stock_id == stock_id)
    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    rows = list(db.scalars(statement.order_by(ResearchAnalysis.created_at.desc()).limit(limit).offset(offset)).all())
    return rows, int(total)


def collect_evidence(db: Session, user: User, stock: Stock) -> dict[str, object]:
    gaps: list[str] = []
    fundamental = _fundamental(db, user, stock.id, gaps)
    technical, patterns = _technical(db, stock.id, gaps)
    news = _news(db, stock.id, gaps)
    return pack_evidence(
        stock_id=str(stock.id),
        symbol=stock.symbol,
        exchange=stock.exchange,
        fundamental=fundamental,
        technical=technical,
        patterns=patterns,
        news=news,
        gaps=gaps,
    )


def _fundamental(db: Session, user: User, stock_id: UUID, gaps: list[str]) -> list[dict[str, object]]:
    try:
        payload = evaluate_stock(db, user, stock_id, None)
    except Exception:
        logger.exception("research fundamental input failed")
        gaps.append("Fundamental comparisons could not be read.")
        return []
    rows = []
    for item in payload["results"]:
        if item["category"] != "fundamental":
            continue
        rows.append(
            {
                "metric_name": item["metric_name"],
                "state": item["state"],
                "stale": item["state"] == "stale_data",
                "explanation": item["explanation"],
                "as_of": item["as_of"].isoformat() if item["as_of"] is not None else None,
                "value": item["value"],
            }
        )
    if not rows:
        gaps.append("No fundamental comparisons are stored.")
    return rows


def _technical(db: Session, stock_id: UUID, gaps: list[str]) -> tuple[dict[str, object] | None, list[dict[str, object]]]:
    try:
        from app.data_providers.market_data import get_market_data_provider
        from app.services.technical_cache import get_technical_cache
        from app.services.technical_service import get_technical_analysis

        analysis = get_technical_analysis(
            db,
            stock_id,
            provider=get_market_data_provider(),
            cache=get_technical_cache(),
            ttl_seconds=settings.market_data_history_ttl_seconds,
        )
    except Exception:
        logger.exception("research technical input failed")
        gaps.append("Technical analysis could not be read.")
        return None, []
    technical = {
        "category": analysis.conclusion.category,
        "text": analysis.conclusion.text,
        "conflicts": list(analysis.conclusion.conflicts),
        "invalidation": list(analysis.conclusion.invalidation),
        "freshness": analysis.freshness,
        "price_as_of": analysis.price_as_of.isoformat() if analysis.price_as_of else None,
        "kind": "detector",
    }
    patterns = [
        {
            "pattern_type": pattern.pattern_type,
            "status": pattern.status,
            "as_of": pattern.confirmation_timestamp.isoformat() if pattern.confirmation_timestamp else None,
            "kind": "detector",
        }
        for pattern in analysis.patterns
        if pattern.status in {"confirmed", "invalidated", "completed"}
    ]
    return technical, patterns


def _news(db: Session, stock_id: UUID, gaps: list[str]) -> list[dict[str, object]]:
    try:
        rows, _total = list_news(
            db,
            stock_id=stock_id,
            sector=None,
            source=None,
            sentiment=None,
            published_from=None,
            published_to=None,
            window_days=settings.news_default_window_days,
            limit=5,
            offset=0,
        )
        readings = sentiment_for(db, [row.id for row in rows])
    except Exception:
        logger.exception("research news input failed")
        gaps.append("Linked news could not be read.")
        return []
    if not rows:
        gaps.append("No recent confirmed articles are linked to this stock.")
    items = []
    for row in rows:
        reading = readings.get(row.id)
        label = reading.sentiment.value if reading is not None and hasattr(reading.sentiment, "value") else None
        items.append(
            {
                "article_id": str(row.id),
                "title": row.title,
                "url": row.url,
                "source": row.source,
                "published_at": row.published_at.isoformat(),
                "sentiment": label,
                "kind": "stored_article",
            }
        )
    return items


def _reusable(db: Session, user_id: UUID, stock_id: UUID, digest: str) -> ResearchAnalysis | None:
    cutoff = datetime.now(UTC) - timedelta(minutes=settings.ai_reuse_minutes)
    return db.scalar(
        select(ResearchAnalysis)
        .where(
            ResearchAnalysis.user_id == user_id,
            ResearchAnalysis.stock_id == stock_id,
            ResearchAnalysis.input_hash == digest,
            ResearchAnalysis.created_at >= cutoff,
        )
        .order_by(ResearchAnalysis.created_at.desc())
        .limit(1)
    )


def _status_without_model(score: dict[str, object]) -> str:
    if score["aggregate"] == "insufficient_data":
        return "insufficient_data"
    if score["aggregate"] == "partial":
        return "partial"
    return "complete"
