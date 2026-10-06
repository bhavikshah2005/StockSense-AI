"""Retrieve, validate, cache, and store Indian market data.

Routes call this module. Vendor HTTP stays inside a MarketDataProvider.
A future worker can call `sync_historical_prices`. This process does not schedule that work.
"""

import logging
import threading
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.data_providers.market_data.base import STORAGE_INTERVALS, InstrumentRef, MarketDataProvider
from app.data_providers.market_data.errors import (
    INVALID_RANGE,
    MALFORMED,
    NOT_CONFIGURED,
    NOT_FOUND,
    TIMEOUT,
    UNAVAILABLE,
    UNSUPPORTED_EXCHANGE,
    UNSUPPORTED_INTERVAL,
    MarketDataError,
)
from app.markets.calendar import MarketCalendar
from app.markets.profile import active_market
from app.markets.time import IST
from app.models import Stock, StockPrice
from app.schemas.market_data import MarketStatusResponse, PriceBarResponse, PriceHistoryResponse, QuoteResponse
from app.schemas.stock import StockDetail
from app.services.market_validation import validate_bar, validate_quote, validate_status
from app.services.quote_cache import QuoteCache

logger = logging.getLogger(__name__)

_guard = threading.Lock()
_stock_locks: dict[str, threading.Lock] = {}


def get_stock_detail(db: Session, stock_id: UUID) -> StockDetail:
    stock = _listing(db, stock_id)
    profile = active_market()
    return StockDetail(
        id=stock.id,
        symbol=stock.symbol,
        company_name=stock.company_name,
        exchange=stock.exchange,
        sector=stock.sector,
        industry=stock.industry,
        currency=stock.currency,
        country=stock.country,
        country_name=profile.country_name,
        isin=stock.isin,
    )


def get_quote(
    db: Session,
    stock_id: UUID,
    *,
    provider: MarketDataProvider,
    cache: QuoteCache,
    ttl_seconds: int,
    now: datetime | None = None,
) -> QuoteResponse:
    stock = _listing(db, stock_id)
    cached = cache.get(stock.id)
    if cached is not None:
        return cached
    with _lock_for(stock.id):
        cached = cache.get(stock.id)
        if cached is not None:
            return cached
        instrument = _instrument(stock)
        try:
            quote = provider.get_quote(instrument)
        except MarketDataError as exc:
            _log_provider(provider, exc.code)
            raise
        except TimeoutError:
            _log_provider(provider, TIMEOUT)
            raise MarketDataError(TIMEOUT) from None
        except OSError:
            _log_provider(provider, UNAVAILABLE)
            raise MarketDataError(UNAVAILABLE) from None
        checked = validate_quote(quote, instrument)
        fetched_at = now or datetime.now(UTC)
        if fetched_at.tzinfo is None:
            raise MarketDataError(MALFORMED)
        response = QuoteResponse(
            stock_id=stock.id,
            symbol=checked.symbol,
            exchange=checked.exchange,
            currency=checked.currency,
            current_price=checked.current_price,
            previous_close=checked.previous_close,
            change=checked.change,
            change_percent=checked.change_percent,
            open=checked.open,
            high=checked.high,
            low=checked.low,
            volume=checked.volume,
            market_timestamp=checked.market_timestamp,
            fetched_at=fetched_at,
            delayed=checked.delayed,
            delay_minutes=checked.delay_minutes,
        )
        cache.put(response, ttl_seconds)
        return response


def list_prices(
    db: Session,
    stock_id: UUID,
    *,
    interval: str,
    start: date | None,
    end: date | None,
) -> PriceHistoryResponse:
    stock = _listing(db, stock_id)
    _require_storage_interval(interval)
    statement = select(StockPrice).where(
        StockPrice.stock_id == stock.id,
        StockPrice.interval == interval,
    )
    if start is not None:
        statement = statement.where(StockPrice.timestamp >= _ist_start(start))
    if end is not None:
        statement = statement.where(StockPrice.timestamp < _ist_start(end + timedelta(days=1)))
    rows = db.scalars(statement.order_by(StockPrice.timestamp)).all()
    return PriceHistoryResponse(
        stock_id=stock.id,
        interval=interval,
        bars=[
            PriceBarResponse(
                stock_id=stock.id,
                timestamp=row.timestamp,
                interval=row.interval,
                open=row.open,
                high=row.high,
                low=row.low,
                close=row.close,
                adjusted_close=row.adjusted_close,
                volume=row.volume,
            )
            for row in rows
        ],
    )


def sync_historical_prices(
    db: Session,
    stock_id: UUID,
    *,
    provider: MarketDataProvider,
    interval: str,
    start: date | None,
    end: date | None,
) -> int:
    """Upsert bars for one listing. The first sync requires an explicit start date."""
    stock = _listing(db, stock_id)
    _require_storage_interval(interval)
    if not provider.supported_intervals:
        raise MarketDataError(NOT_CONFIGURED)
    if interval not in provider.supported_intervals:
        raise MarketDataError(UNSUPPORTED_INTERVAL)
    range_end = end or datetime.now(UTC).astimezone(IST).date()
    range_start = start if start is not None else _resume_date(db, stock.id, interval)
    if range_start > range_end:
        return 0
    instrument = _instrument(stock)
    try:
        bars = provider.get_historical_prices(
            instrument,
            start=range_start,
            end=range_end,
            interval=interval,
        )
    except MarketDataError as exc:
        _log_provider(provider, exc.code)
        raise
    except TimeoutError:
        _log_provider(provider, TIMEOUT)
        raise MarketDataError(TIMEOUT) from None
    except OSError:
        _log_provider(provider, UNAVAILABLE)
        raise MarketDataError(UNAVAILABLE) from None
    seen: set[datetime] = set()
    values: list[dict[str, object]] = []
    for bar in bars:
        validate_bar(bar, interval)
        bar_day = bar.timestamp.astimezone(IST).date()
        if bar_day < range_start or bar_day > range_end:
            raise MarketDataError(MALFORMED)
        if bar.timestamp in seen:
            raise MarketDataError(MALFORMED)
        seen.add(bar.timestamp)
        values.append(
            {
                "stock_id": stock.id,
                "timestamp": bar.timestamp,
                "interval": bar.interval,
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "adjusted_close": bar.adjusted_close,
                "volume": bar.volume,
            }
        )
    if not values:
        return 0
    statement = pg_insert(StockPrice).values(values)
    statement = statement.on_conflict_do_update(
        index_elements=["stock_id", "interval", "timestamp"],
        set_={
            "open": statement.excluded.open,
            "high": statement.excluded.high,
            "low": statement.excluded.low,
            "close": statement.excluded.close,
            "adjusted_close": statement.excluded.adjusted_close,
            "volume": statement.excluded.volume,
        },
    )
    db.execute(statement)
    db.commit()
    return len(values)


def get_market_status(
    exchange: str,
    *,
    provider: MarketDataProvider,
    calendar: MarketCalendar,
) -> MarketStatusResponse:
    code = exchange.strip().upper()
    if code not in active_market().exchanges:
        raise MarketDataError(UNSUPPORTED_EXCHANGE)
    try:
        reported = provider.get_market_status(code)
    except MarketDataError as exc:
        if exc.code != NOT_CONFIGURED:
            _log_provider(provider, exc.code)
            raise
        reported = None
    except TimeoutError:
        _log_provider(provider, TIMEOUT)
        raise MarketDataError(TIMEOUT) from None
    except OSError:
        _log_provider(provider, UNAVAILABLE)
        raise MarketDataError(UNAVAILABLE) from None
    if reported is None:
        reported = calendar.status(code)
    if reported is None:
        raise MarketDataError(NOT_CONFIGURED)
    validate_status(reported, code)
    return MarketStatusResponse(
        exchange=reported.exchange,
        status=reported.status,
        observed_at=reported.observed_at,
        source=reported.source,
    )


def load_listing(db: Session, stock_id: UUID) -> Stock:
    return _listing(db, stock_id)


def _listing(db: Session, stock_id: UUID) -> Stock:
    stock = db.get(Stock, stock_id)
    if stock is None or not stock.is_active:
        raise MarketDataError(NOT_FOUND)
    profile = active_market()
    if stock.exchange not in profile.exchanges:
        raise MarketDataError(UNSUPPORTED_EXCHANGE)
    if stock.country != profile.country or stock.currency != profile.currency:
        raise MarketDataError(UNSUPPORTED_EXCHANGE)
    return stock


def _instrument(stock: Stock) -> InstrumentRef:
    return InstrumentRef(
        symbol=stock.symbol,
        exchange=stock.exchange,
        currency=stock.currency,
        country=stock.country,
    )


def _require_storage_interval(interval: str) -> None:
    if interval not in STORAGE_INTERVALS:
        raise MarketDataError(UNSUPPORTED_INTERVAL)


def _resume_date(db: Session, stock_id: UUID, interval: str) -> date:
    latest = db.scalar(
        select(func.max(StockPrice.timestamp)).where(
            StockPrice.stock_id == stock_id,
            StockPrice.interval == interval,
        )
    )
    if latest is None:
        raise MarketDataError(INVALID_RANGE)
    if latest.tzinfo is None:
        raise MarketDataError(MALFORMED)
    return latest.astimezone(IST).date()


def _ist_start(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=IST)


def _lock_for(stock_id: UUID) -> threading.Lock:
    key = str(stock_id)
    with _guard:
        lock = _stock_locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _stock_locks[key] = lock
        return lock


def _log_provider(provider: MarketDataProvider, code: str) -> None:
    logger.warning("market data provider error code=%s provider=%s", code, provider.name)
