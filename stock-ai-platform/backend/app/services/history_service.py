"""Load a chart range from PostgreSQL, filling only the missing spans from the provider."""

import logging
import threading
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data_providers.market_data.base import MarketDataProvider
from app.data_providers.market_data.errors import INVALID_QUERY, MarketDataError
from app.markets.ranges import (
    MAX_BARS,
    choose_interval,
    limit_intraday,
    missing_spans,
    resolve_window,
)
from app.markets.time import IST
from app.models import StockPrice
from app.schemas.market_data import (
    HistoryBar,
    HistoryPerformance,
    HistoryResponse,
    HistoryStock,
)
from app.services.history_cache import HistoryCache, history_cache_key
from app.services.history_math import performance_and_extremes
from app.services.market_data_service import load_listing, sync_historical_prices

logger = logging.getLogger(__name__)

_guard = threading.Lock()
_locks: dict[str, threading.Lock] = {}


def get_history(
    db: Session,
    stock_id: UUID,
    *,
    provider: MarketDataProvider,
    cache: HistoryCache,
    ttl_seconds: int,
    max_years: int,
    range_name: str | None = None,
    start: date | None = None,
    end: date | None = None,
    interval: str | None = None,
    today: date | None = None,
    now: datetime | None = None,
) -> HistoryResponse:
    stock = load_listing(db, stock_id)
    as_of = today or datetime.now(UTC).astimezone(IST).date()
    window_start, window_end, resolved_range = resolve_window(
        range_name=range_name,
        start=start,
        end=end,
        today=as_of,
        max_years=max_years,
    )
    if window_end > as_of:
        window_end = as_of
    if window_start > window_end:
        raise MarketDataError(INVALID_QUERY)
    chosen = choose_interval(
        range_name=resolved_range,
        requested=interval,
        supported=provider.supported_intervals,
    )
    limit_intraday(chosen, window_start, window_end)
    cache_key = history_cache_key(stock.id, chosen, window_start, window_end)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    with _lock(f"{stock.id}:{chosen}"):
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        try:
            _fill_missing(db, stock.id, provider, chosen, window_start, window_end)
        except MarketDataError:
            if not _rows(db, stock.id, chosen, window_start, window_end):
                raise
            logger.warning("history sync stopped after stored bars remained stock=%s", stock.id)
            return _response(
                db,
                stock_id=stock.id,
                symbol=stock.symbol,
                company_name=stock.company_name,
                exchange=stock.exchange,
                currency=stock.currency,
                interval=chosen,
                range_name=resolved_range,
                start=window_start,
                end=window_end,
                now=now or datetime.now(UTC),
            )
        response = _response(
            db,
            stock_id=stock.id,
            symbol=stock.symbol,
            company_name=stock.company_name,
            exchange=stock.exchange,
            currency=stock.currency,
            interval=chosen,
            range_name=resolved_range,
            start=window_start,
            end=window_end,
            now=now or datetime.now(UTC),
        )
        cache.put(cache_key, response, ttl_seconds)
        return response


def _fill_missing(
    db: Session,
    stock_id: UUID,
    provider: MarketDataProvider,
    interval: str,
    start: date,
    end: date,
) -> None:
    spans = missing_spans(_stored_days(db, stock_id, interval, start, end), start, end)
    if not spans:
        return
    for span_start, span_end in spans:
        sync_historical_prices(
            db,
            stock_id,
            provider=provider,
            interval=interval,
            start=span_start,
            end=span_end,
        )


def _stored_days(db: Session, stock_id: UUID, interval: str, start: date, end: date) -> list[date]:
    rows = _rows(db, stock_id, interval, start, end)
    return [row.timestamp.astimezone(IST).date() for row in rows]


def _rows(db: Session, stock_id: UUID, interval: str, start: date, end: date) -> list[StockPrice]:
    statement = (
        select(StockPrice)
        .where(
            StockPrice.stock_id == stock_id,
            StockPrice.interval == interval,
            StockPrice.timestamp >= datetime.combine(start, time.min, tzinfo=IST),
            StockPrice.timestamp < datetime.combine(end + timedelta(days=1), time.min, tzinfo=IST),
        )
        .order_by(StockPrice.timestamp)
    )
    rows = list(db.scalars(statement).all())
    if len(rows) > MAX_BARS:
        return rows[-MAX_BARS:]
    return rows


def _response(
    db: Session,
    *,
    stock_id: UUID,
    symbol: str,
    company_name: str,
    exchange: str,
    currency: str,
    interval: str,
    range_name: str | None,
    start: date,
    end: date,
    now: datetime,
) -> HistoryResponse:
    rows = _rows(db, stock_id, interval, start, end)
    summary = performance_and_extremes(rows)
    performance = None
    period_high = None
    period_low = None
    if summary is not None:
        start_price, end_price, change, percent, period_high, period_low = summary
        performance = HistoryPerformance(
            start_price=start_price,
            end_price=end_price,
            change=change,
            change_percent=percent,
        )
    reported_start = rows[0].timestamp.astimezone(IST).date() if len(rows) == MAX_BARS else start
    return HistoryResponse(
        stock=HistoryStock(
            id=stock_id,
            symbol=symbol,
            company_name=company_name,
            exchange=exchange,
            currency=currency,
        ),
        interval=interval,
        range=range_name,
        start_date=reported_start,
        end_date=end,
        market_timestamp=rows[-1].timestamp if rows else None,
        fetched_at=now,
        data=[
            HistoryBar(
                timestamp=row.timestamp,
                open=row.open,
                high=row.high,
                low=row.low,
                close=row.close,
                adjusted_close=row.adjusted_close,
                volume=row.volume,
            )
            for row in rows
        ],
        performance=performance,
        period_high=period_high,
        period_low=period_low,
    )


def _lock(key: str) -> threading.Lock:
    with _guard:
        lock = _locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _locks[key] = lock
        return lock
