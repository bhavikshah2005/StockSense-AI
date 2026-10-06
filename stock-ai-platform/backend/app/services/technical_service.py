"""Load stored daily bars, run the analysis engine, and persist the result."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.analysis.bars import Bar
from app.analysis.config import DETECTOR_VERSION, INDICATOR_VERSION
from app.analysis.engine import Analysis, analyze
from app.analysis.patterns.common import PatternHit
from app.data_providers.market_data.base import MarketDataProvider
from app.data_providers.market_data.errors import INVALID_RANGE, NOT_CONFIGURED, UNSUPPORTED_INTERVAL, MarketDataError
from app.markets.time import IST
from app.models import Stock, StockPrice, TechnicalIndicator, TechnicalPattern
from app.schemas.technical import (
    BoundaryPoint,
    BreakoutBlock,
    ConclusionBlock,
    IndicatorBlock,
    PatternBlock,
    PatternHistoryResponse,
    PivotPoint,
    SeriesPoint,
    TechnicalAnalysisResponse,
    TechnicalStock,
    TechnicalSummaryResponse,
    ZoneBlock,
)
from app.services.market_data_service import load_listing, sync_historical_prices
from app.services.technical_cache import TechnicalCache, technical_cache_key

logger = logging.getLogger(__name__)

MAX_RANGE_DAYS = 1100
DEFAULT_RANGE_DAYS = 800
STALE_DAYS = 7
MIN_STORED_BARS = 60
PATTERN_DEFINITIONS = {
    "head_and_shoulders": "Three swing highs, with the middle high above the other two, and a neckline through the intervening lows.",
    "inverse_head_and_shoulders": "Three swing lows, with the middle low below the other two, and a neckline through the intervening highs.",
    "double_top": "Two swing highs within the level tolerance, separated by a retracement.",
    "double_bottom": "Two swing lows within the level tolerance, separated by a rebound.",
    "triple_top": "Three swing highs within the level tolerance, with a retracement between each pair.",
    "triple_bottom": "Three swing lows within the level tolerance, with a rebound between each pair.",
    "ascending_triangle": "A near-flat upper boundary and a rising lower boundary, each tested by at least two swings.",
    "descending_triangle": "A near-flat lower boundary and a falling upper boundary, each tested by at least two swings.",
    "symmetrical_triangle": "A falling upper boundary and a rising lower boundary that narrow the range.",
    "rising_wedge": "Two rising, converging boundaries. The label does not by itself mean a reversal.",
    "falling_wedge": "Two falling, converging boundaries. The label does not by itself mean a reversal.",
    "rectangle": "A near-flat upper boundary and lower boundary with repeated tests.",
    "bull_flag": "A rise of at least 10 percent followed by a smaller consolidation.",
    "bear_flag": "A decline of at least 10 percent followed by a smaller consolidation.",
    "higher_highs_higher_lows": "The latest confirmed swing high and swing low are both above the prior pair.",
    "lower_highs_lower_lows": "The latest confirmed swing high and swing low are both below the prior pair.",
}


def get_technical_analysis(
    db: Session,
    stock_id: UUID,
    *,
    provider: MarketDataProvider,
    cache: TechnicalCache,
    ttl_seconds: int,
    interval: str = "1d",
    start: date | None = None,
    end: date | None = None,
    today: date | None = None,
    now: datetime | None = None,
) -> TechnicalAnalysisResponse:
    stock = load_listing(db, stock_id)
    as_of = today or datetime.now(UTC).astimezone(IST).date()
    window_end = end or as_of
    window_start = start or (window_end - timedelta(days=DEFAULT_RANGE_DAYS))
    _validate_window(interval, window_start, window_end)
    bars = _ensure_bars(db, stock, provider, interval, window_start, window_end, as_of)
    price_as_of = bars[-1].timestamp if bars else None
    key = technical_cache_key(stock.id, interval, window_start, window_end, price_as_of.isoformat() if price_as_of else "none")
    cached = cache.get(key)
    if cached is not None:
        return cached
    analysis = analyze(bars, interval)
    calculated = now or datetime.now(UTC)
    _persist(db, stock.id, interval, analysis, calculated)
    response = _response(stock, interval, analysis, calculated, as_of)
    cache.put(key, response, ttl_seconds)
    return response


def get_pattern_history(
    db: Session,
    stock_id: UUID,
    *,
    provider: MarketDataProvider,
    cache: TechnicalCache,
    ttl_seconds: int,
    interval: str = "1d",
    pattern_type: str | None = None,
    status: str | None = None,
    start: date | None = None,
    end: date | None = None,
    limit: int = 20,
    offset: int = 0,
    today: date | None = None,
) -> PatternHistoryResponse:
    allowed_status = {"developing", "confirmed", "invalidated", "completed", "uncertain", "insufficient_data"}
    if status is not None and status not in allowed_status:
        raise MarketDataError(INVALID_RANGE)
    if limit < 1 or limit > 50 or offset < 0:
        raise MarketDataError(INVALID_RANGE)
    analysis = get_technical_analysis(
        db,
        stock_id,
        provider=provider,
        cache=cache,
        ttl_seconds=ttl_seconds,
        interval=interval,
        start=start,
        end=end,
        today=today,
    )
    query = select(TechnicalPattern).where(
        TechnicalPattern.stock_id == analysis.stock.id,
        TechnicalPattern.interval == interval,
        TechnicalPattern.detector_version == DETECTOR_VERSION,
    )
    if pattern_type:
        query = query.where(TechnicalPattern.pattern_type == pattern_type)
    if status:
        query = query.where(TechnicalPattern.status == status)
    if start is not None:
        query = query.where(TechnicalPattern.start_timestamp >= _start_bound(start))
    if end is not None:
        query = query.where(TechnicalPattern.end_timestamp < _end_bound(end))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(query.order_by(TechnicalPattern.start_timestamp.desc()).limit(limit).offset(offset)).all()
    return PatternHistoryResponse(
        stock=analysis.stock,
        interval=interval,
        total=int(total),
        limit=limit,
        offset=offset,
        results=[_pattern_from_row(row) for row in rows],
    )


def get_technical_summary(
    db: Session,
    stock_id: UUID,
    *,
    provider: MarketDataProvider,
    cache: TechnicalCache,
    ttl_seconds: int,
    interval: str = "1d",
    today: date | None = None,
) -> TechnicalSummaryResponse:
    analysis = get_technical_analysis(
        db,
        stock_id,
        provider=provider,
        cache=cache,
        ttl_seconds=ttl_seconds,
        interval=interval,
        today=today,
    )
    return TechnicalSummaryResponse(
        stock=analysis.stock,
        interval=analysis.interval,
        freshness=analysis.freshness,
        price_as_of=analysis.price_as_of,
        calculated_at=analysis.calculated_at,
        conclusion=analysis.conclusion,
        limitations=analysis.limitations,
    )


def _validate_window(interval: str, start: date, end: date) -> None:
    if interval != "1d":
        raise MarketDataError(UNSUPPORTED_INTERVAL)
    if start > end or (end - start).days > MAX_RANGE_DAYS:
        raise MarketDataError(INVALID_RANGE)


def _ensure_bars(
    db: Session,
    stock: Stock,
    provider: MarketDataProvider,
    interval: str,
    start: date,
    end: date,
    today: date,
) -> list[Bar]:
    stored = _read_bars(db, stock.id, interval, start, end)
    last_session = stored[-1].timestamp.astimezone(IST).date() if stored else None
    # Refresh when the newest daily bar is behind the previous calendar day, so a new session is stored.
    caught_up = last_session is not None and last_session >= today - timedelta(days=1)
    if len(stored) >= MIN_STORED_BARS and caught_up:
        return stored
    if not provider.supported_intervals:
        if stored:
            return stored
        raise MarketDataError(NOT_CONFIGURED)
    try:
        sync_historical_prices(db, stock.id, provider=provider, interval=interval, start=start, end=end)
    except MarketDataError:
        if stored:
            logger.warning("technical analysis kept stored bars after a provider error")
            return stored
        raise
    return _read_bars(db, stock.id, interval, start, end)


def _read_bars(db: Session, stock_id: UUID, interval: str, start: date, end: date) -> list[Bar]:
    rows = db.scalars(
        select(StockPrice)
        .where(
            StockPrice.stock_id == stock_id,
            StockPrice.interval == interval,
            StockPrice.timestamp >= _start_bound(start),
            StockPrice.timestamp < _end_bound(end),
        )
        .order_by(StockPrice.timestamp)
    ).all()
    return [
        Bar(row.timestamp, row.open, row.high, row.low, row.close, int(row.volume))
        for row in rows
    ]


def _persist(db: Session, stock_id: UUID, interval: str, analysis: Analysis, calculated: datetime) -> None:
    if not analysis.bars:
        return
    last = analysis.bars[-1]
    indicators = analysis.indicators
    values = {
        "stock_id": stock_id,
        "interval": interval,
        "calculation_version": INDICATOR_VERSION,
        "timestamp": last.timestamp,
        "rsi_14": indicators.rsi_14,
        "macd": indicators.macd,
        "macd_signal": indicators.macd_signal,
        "macd_histogram": indicators.macd_histogram,
        "sma_20": indicators.sma_20,
        "sma_50": indicators.sma_50,
        "sma_100": indicators.sma_100,
        "sma_200": indicators.sma_200,
        "ema_20": indicators.ema_20,
        "ema_50": indicators.ema_50,
        "volatility": indicators.volatility,
        "average_volume": indicators.average_volume,
        "additional_indicators": {
            "price_field": "close",
            "performance": {key: _text(value) for key, value in indicators.performance.items()},
            "week52_high": _text(indicators.week52_high),
            "week52_low": _text(indicators.week52_low),
            "volatility_method": "sample_log_return_stdev_annualized_percent",
        },
        "updated_at": calculated,
    }
    statement = pg_insert(TechnicalIndicator).values(values)
    statement = statement.on_conflict_do_update(
        index_elements=["stock_id", "interval", "timestamp", "calculation_version"],
        set_={key: statement.excluded[key] for key in values if key not in {"stock_id", "interval", "timestamp", "calculation_version"}},
    )
    db.execute(statement)
    for pattern in analysis.patterns:
        _persist_pattern(db, stock_id, interval, analysis, pattern, calculated)
    db.commit()


def _persist_pattern(
    db: Session,
    stock_id: UUID,
    interval: str,
    analysis: Analysis,
    pattern: PatternHit,
    calculated: datetime,
) -> None:
    start_at = analysis.bars[pattern.start_index].timestamp
    end_at = analysis.bars[pattern.end_index].timestamp
    confirmed_at = analysis.bars[pattern.confirmation_index].timestamp if pattern.confirmation_index is not None else None
    invalidated_at = end_at if pattern.status == "invalidated" else None
    payload = {
        "stock_id": stock_id,
        "interval": interval,
        "pattern_type": pattern.pattern_type,
        "direction": pattern.direction,
        "status": pattern.status,
        "start_timestamp": start_at,
        "end_timestamp": end_at,
        "confirmed_at": confirmed_at,
        "invalidated_at": invalidated_at,
        "key_levels": pattern.levels,
        "pivot_evidence": [
            {
                "timestamp": analysis.bars[pivot.index].timestamp.isoformat(),
                "confirmed_at": pivot.confirmed_at.isoformat(),
                "kind": pivot.kind,
                "price": format(pivot.price.quantize(Decimal("0.0001")), "f"),
            }
            for pivot in pattern.pivots
            if pivot.index < len(analysis.bars)
        ],
        "evidence_summary": pattern.evidence[:2000],
        "detector_version": DETECTOR_VERSION,
        "source_price_as_of": analysis.bars[-1].timestamp,
        "calculated_at": calculated,
        "updated_at": calculated,
    }
    statement = pg_insert(TechnicalPattern).values(payload)
    statement = statement.on_conflict_do_update(
        index_elements=["stock_id", "interval", "pattern_type", "start_timestamp", "detector_version"],
        set_={key: statement.excluded[key] for key in payload if key not in {"stock_id", "interval", "pattern_type", "start_timestamp", "detector_version"}},
    )
    db.execute(statement)


def _response(
    stock: Stock,
    interval: str,
    analysis: Analysis,
    calculated: datetime,
    today: date,
) -> TechnicalAnalysisResponse:
    price_as_of = analysis.bars[-1].timestamp if analysis.bars else None
    if price_as_of is None:
        freshness = "insufficient"
    elif price_as_of.astimezone(IST).date() < today - timedelta(days=STALE_DAYS):
        freshness = "stale"
    else:
        freshness = "current"
    indicators = analysis.indicators
    return TechnicalAnalysisResponse(
        stock=TechnicalStock(id=stock.id, symbol=stock.symbol, exchange=stock.exchange, company_name=stock.company_name),
        interval=interval,
        freshness=freshness,
        price_as_of=price_as_of,
        calculated_at=calculated,
        indicators=IndicatorBlock(
            rsi_14=_text(indicators.rsi_14),
            macd=_text(indicators.macd),
            macd_signal=_text(indicators.macd_signal),
            macd_histogram=_text(indicators.macd_histogram),
            sma_20=_text(indicators.sma_20),
            sma_50=_text(indicators.sma_50),
            sma_100=_text(indicators.sma_100),
            sma_200=_text(indicators.sma_200),
            ema_20=_text(indicators.ema_20),
            ema_50=_text(indicators.ema_50),
            volatility=_text(indicators.volatility),
            average_volume=_text(indicators.average_volume),
            volume=indicators.volume,
            week52_high=_text(indicators.week52_high),
            week52_low=_text(indicators.week52_low),
            distance_from_high_percent=_text(indicators.distance_from_high_percent),
            distance_from_low_percent=_text(indicators.distance_from_low_percent),
            performance={key: _text(value) for key, value in indicators.performance.items()},
            as_of=price_as_of,
        ),
        series=[
            SeriesPoint(
                timestamp=bar.timestamp,
                close=format(bar.close, "f"),
                sma_20=_text(indicators.sma_20_series[index]),
                sma_50=_text(indicators.sma_50_series[index]),
                volume=bar.volume if bar.volume > 0 else None,
            )
            for index, bar in enumerate(analysis.bars)
        ],
        patterns=[_pattern_block(analysis, pattern) for pattern in analysis.patterns],
        zones=[
            ZoneBlock(
                kind=zone.kind,
                lower=zone.lower,
                upper=zone.upper,
                tests=zone.tests,
                last_test=analysis.bars[zone.last_test_index].timestamp if analysis.bars else None,
                status=zone.status,
                method="clustered swing pivots within 1.5 percent of the cluster average",
            )
            for zone in analysis.zones
        ],
        breakouts=[
            BreakoutBlock(
                source=note.source,
                side=note.side,
                status=note.status,
                boundary=note.boundary,
                confirmation_met=note.confirmation_met,
                volume_evidence=note.volume_evidence,
                missing=list(note.missing),
            )
            for note in analysis.breakouts
        ],
        conclusion=ConclusionBlock(
            category=analysis.conclusion.category,
            text=analysis.conclusion.text,
            conflicts=list(analysis.conclusion.conflicts),
            invalidation=list(analysis.conclusion.invalidation),
        ),
        limitations=list(analysis.limitations),
        indicator_version=INDICATOR_VERSION,
        detector_version=DETECTOR_VERSION,
    )


def _pattern_block(analysis: Analysis, pattern: PatternHit) -> PatternBlock:
    return PatternBlock(
        pattern_type=pattern.pattern_type,
        direction=pattern.direction,
        status=pattern.status,
        start_timestamp=analysis.bars[pattern.start_index].timestamp,
        end_timestamp=analysis.bars[pattern.end_index].timestamp,
        levels=pattern.levels,
        boundaries={
            name: [BoundaryPoint(timestamp=analysis.bars[index].timestamp, price=price) for index, price in points]
            for name, points in pattern.boundaries.items()
        },
        pivots=[
            PivotPoint(
                timestamp=pivot.timestamp,
                confirmed_at=pivot.confirmed_at,
                kind=pivot.kind,
                price=format(pivot.price.quantize(Decimal("0.0001")), "f"),
            )
            for pivot in pattern.pivots
        ],
        confirmation_met=pattern.confirmation_index is not None,
        confirmation_timestamp=analysis.bars[pattern.confirmation_index].timestamp if pattern.confirmation_index is not None else None,
        invalidation=pattern.invalidation_text,
        evidence=pattern.evidence,
        limitations=list(pattern.limitations),
        quality=pattern.quality,
        detector_version=DETECTOR_VERSION,
        definition=PATTERN_DEFINITIONS.get(pattern.pattern_type, "A rule-based reading of stored prices."),
    )


def _pattern_from_row(row: TechnicalPattern) -> PatternBlock:
    boundaries: dict[str, list[BoundaryPoint]] = {}
    return PatternBlock(
        pattern_type=row.pattern_type,
        direction=row.direction,
        status=row.status,
        start_timestamp=row.start_timestamp,
        end_timestamp=row.end_timestamp,
        levels={key: str(value) for key, value in row.key_levels.items()},
        boundaries=boundaries,
        pivots=[
            PivotPoint(
                timestamp=datetime.fromisoformat(str(item["timestamp"])),
                confirmed_at=datetime.fromisoformat(str(item["confirmed_at"])),
                kind=str(item["kind"]),
                price=str(item["price"]),
            )
            for item in row.pivot_evidence
            if isinstance(item, dict)
        ],
        confirmation_met=row.confirmed_at is not None,
        confirmation_timestamp=row.confirmed_at,
        invalidation="See the current technical analysis for the invalidation rule.",
        evidence=row.evidence_summary,
        limitations=[],
        quality="clear",
        detector_version=row.detector_version,
        definition=PATTERN_DEFINITIONS.get(row.pattern_type, "A rule-based reading of stored prices."),
    )


def _text(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value, "f")


def _start_bound(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=IST)


def _end_bound(day: date) -> datetime:
    return datetime.combine(day + timedelta(days=1), time.min, tzinfo=IST)
