import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.data_providers.market_data import get_market_data_provider
from app.data_providers.market_data.india import UnconfiguredMarketDataProvider
from app.data_providers.market_data.base import InstrumentRef, MarketDataProvider, MarketStatus, PriceBar, Quote
from app.data_providers.market_data.errors import MarketDataError
from app.main import app
from app.markets.ranges import missing_spans, resolve_window
from app.markets.time import IST
from app.models import Stock, StockPrice
from app.services.history_cache import MemoryHistoryCache, RedisHistoryCache, get_history_cache, history_cache_key
from app.services.history_math import performance_and_extremes
from app.services.history_service import get_history
from app.services.market_validation import validate_bar
from tests.isolation import hide_committed_market_rows

PASSWORD = "Validpass1"
ORIGIN = "http://localhost:5173"
TODAY = date(2026, 9, 23)


class RecordingProvider(MarketDataProvider):
    def __init__(self, *, intervals: frozenset[str] = frozenset({"1d"}), fail: Exception | None = None) -> None:
        self._intervals = intervals
        self.fail = fail
        self.calls = 0
        self.spans: list[tuple[date, date, str]] = []

    @property
    def name(self) -> str:
        return "recording"

    @property
    def supported_intervals(self) -> frozenset[str]:
        return self._intervals

    def get_quote(self, instrument: InstrumentRef) -> Quote:
        raise MarketDataError("not_configured")

    def get_historical_prices(
        self,
        instrument: InstrumentRef,
        *,
        start: date,
        end: date,
        interval: str,
    ) -> list[PriceBar]:
        self.calls += 1
        self.spans.append((start, end, interval))
        if self.fail is not None:
            raise self.fail
        return _weekday_bars(start, end, interval)

    def get_market_status(self, exchange: str) -> MarketStatus:
        raise MarketDataError("not_configured")


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.ttls: dict[str, int] = {}

    def get(self, key: str) -> str | None:
        return self.values.get(key)

    def setex(self, key: str, ttl: int, value: str) -> None:
        self.values[key] = value
        self.ttls[key] = ttl


def _auth(client: TestClient) -> None:
    response = client.post(
        "/api/auth/register",
        json={
            "email": f"history-{uuid.uuid4().hex}@example.com",
            "password": PASSWORD,
            "full_name": "History Tester",
        },
        headers={"Origin": ORIGIN},
    )
    assert response.status_code == 201, response.text


def _db() -> Session:
    override = app.dependency_overrides[get_db]
    return next(override())


def _tcs(db: Session) -> Stock:
    stock = db.scalar(select(Stock).where(Stock.symbol == "TCS", Stock.exchange == "NSE"))
    assert stock is not None
    hide_committed_market_rows(db, stock.id)
    return stock


def _weekday_bars(start: date, end: date, interval: str, *, broken: bool = False) -> list[PriceBar]:
    bars: list[PriceBar] = []
    day = start
    while day <= end:
        if day.weekday() < 5:
            close = Decimal(3000 + day.day)
            high = Decimal("-1") if broken else close + Decimal("10")
            bars.append(
                PriceBar(
                    timestamp=datetime(day.year, day.month, day.day, 9, 15, tzinfo=IST),
                    interval=interval,
                    open=close - Decimal("5"),
                    high=high,
                    low=close - Decimal("8"),
                    close=close,
                    adjusted_close=close,
                    volume=1000 + day.day,
                )
            )
        day += timedelta(days=1)
    return bars


def _use(provider: MarketDataProvider, cache: MemoryHistoryCache | RedisHistoryCache | None = None) -> None:
    app.dependency_overrides[get_market_data_provider] = lambda: provider
    if cache is not None:
        app.dependency_overrides[get_history_cache] = lambda: cache


def test_ranges_use_ist_calendar_math() -> None:
    start, end, name = resolve_window(range_name="1m", start=None, end=None, today=TODAY, max_years=10)
    assert name == "1m"
    assert end == TODAY
    assert start == date(2026, 8, 23)
    start, end, name = resolve_window(range_name="1y", start=None, end=None, today=TODAY, max_years=10)
    assert name == "1y"
    assert start == date(2025, 9, 23)
    assert end == TODAY
    start, end, _ = resolve_window(range_name="max", start=None, end=None, today=TODAY, max_years=10)
    assert start == date(2016, 9, 23)
    with pytest.raises(MarketDataError):
        resolve_window(range_name="1y", start=date(2026, 1, 1), end=date(2026, 2, 1), today=TODAY, max_years=10)
    with pytest.raises(MarketDataError):
        resolve_window(range_name=None, start=date(2026, 9, 10), end=date(2026, 9, 1), today=TODAY, max_years=10)


def test_weekend_gap_is_not_missing() -> None:
    days = [date(2026, 9, 4), date(2026, 9, 7)]
    assert missing_spans(days, date(2026, 9, 4), date(2026, 9, 7)) == []
    assert missing_spans([], date(2026, 9, 1), date(2026, 9, 10)) == [(date(2026, 9, 1), date(2026, 9, 10))]


def test_history_requires_authentication(client: TestClient) -> None:
    response = client.get(f"/api/stocks/{uuid.uuid4()}/history", params={"range": "1y"})
    assert response.status_code == 401


def test_unconfigured_history_returns_service_error(client: TestClient) -> None:
    _auth(client)
    stock = _tcs(_db())
    _use(UnconfiguredMarketDataProvider())
    response = client.get(f"/api/stocks/{stock.id}/history", params={"range": "1m"})
    assert response.status_code == 503
    assert response.json()["detail"] == "Market data service temporarily unavailable"
    assert "close" not in response.text


def test_custom_range_fetches_weekdays_only(client: TestClient) -> None:
    _auth(client)
    stock = _tcs(_db())
    provider = RecordingProvider()
    _use(provider, MemoryHistoryCache())
    response = client.get(
        f"/api/stocks/{stock.id}/history",
        params={"start_date": "2026-09-01", "end_date": "2026-09-10", "interval": "1d"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["stock"]["symbol"] == "TCS"
    assert body["stock"]["exchange"] == "NSE"
    assert body["stock"]["currency"] == "INR"
    assert body["interval"] == "1d"
    assert provider.calls == 1
    days = [item["timestamp"][8:10] for item in body["data"]]
    assert "06" not in days
    assert "05" not in days
    assert body["performance"]["start_price"] == "3001.0000"
    assert body["performance"]["end_price"] == "3010.0000"
    assert body["period_high"] == "3020.0000"
    assert body["period_low"] == "2993.0000"
    assert body["market_timestamp"] != body["fetched_at"]
    count = _db().scalar(
        select(func.count()).select_from(StockPrice).where(StockPrice.stock_id == stock.id, StockPrice.interval == "1d")
    )
    assert count == len(body["data"])


def test_one_month_and_one_year_windows(client: TestClient) -> None:
    db = _db()
    stock = _tcs(db)
    provider = RecordingProvider()
    cache = MemoryHistoryCache()
    month = get_history(
        db,
        stock.id,
        provider=provider,
        cache=cache,
        ttl_seconds=300,
        max_years=10,
        range_name="1m",
        today=TODAY,
    )
    assert month.start_date == date(2026, 8, 23)
    assert month.end_date == TODAY
    assert month.interval == "1d"
    assert provider.calls == 1
    year = get_history(
        db,
        stock.id,
        provider=provider,
        cache=MemoryHistoryCache(),
        ttl_seconds=300,
        max_years=10,
        range_name="1y",
        today=TODAY,
    )
    assert year.start_date == date(2025, 9, 23)
    assert year.end_date == TODAY
    assert provider.calls == 2
    assert provider.spans[1][0] == date(2025, 9, 23)


def test_postgres_hit_skips_provider(client: TestClient) -> None:
    db = _db()
    stock = _tcs(db)
    for day in (date(2026, 9, 1), date(2026, 9, 2), date(2026, 9, 3), date(2026, 9, 4), date(2026, 9, 7)):
        db.add(_stored(stock.id, day))
    db.commit()
    provider = RecordingProvider()
    body = get_history(
        db,
        stock.id,
        provider=provider,
        cache=MemoryHistoryCache(),
        ttl_seconds=300,
        max_years=10,
        start=date(2026, 9, 1),
        end=date(2026, 9, 7),
        today=TODAY,
    )
    assert provider.calls == 0
    assert len(body.data) == 5
    assert body.performance is not None
    assert body.performance.change == body.performance.end_price - body.performance.start_price


def test_missing_tail_fetches_only_the_gap(client: TestClient) -> None:
    db = _db()
    stock = _tcs(db)
    for day in (date(2026, 9, 1), date(2026, 9, 2), date(2026, 9, 3), date(2026, 9, 4)):
        db.add(_stored(stock.id, day))
    db.commit()
    provider = RecordingProvider()
    get_history(
        db,
        stock.id,
        provider=provider,
        cache=MemoryHistoryCache(),
        ttl_seconds=300,
        max_years=10,
        start=date(2026, 9, 1),
        end=date(2026, 9, 10),
        today=TODAY,
    )
    assert provider.calls == 1
    assert provider.spans[0][0] == date(2026, 9, 5)
    assert provider.spans[0][1] == date(2026, 9, 10)
    again = RecordingProvider()
    get_history(
        db,
        stock.id,
        provider=again,
        cache=MemoryHistoryCache(),
        ttl_seconds=300,
        max_years=10,
        start=date(2026, 9, 1),
        end=date(2026, 9, 10),
        today=TODAY,
    )
    assert again.calls == 0


def test_empty_provider_range_is_empty(client: TestClient) -> None:
    _auth(client)
    stock = _tcs(_db())
    provider = RecordingProvider()
    provider.fail = None
    _use(provider, MemoryHistoryCache())

    class Empty(RecordingProvider):
        def get_historical_prices(self, instrument: InstrumentRef, *, start: date, end: date, interval: str) -> list[PriceBar]:
            self.calls += 1
            return []

    empty = Empty()
    _use(empty, MemoryHistoryCache())
    response = client.get(
        f"/api/stocks/{stock.id}/history",
        params={"start_date": "2026-09-05", "end_date": "2026-09-06", "interval": "1d"},
    )
    assert response.status_code == 200
    assert response.json()["data"] == []
    assert response.json()["performance"] is None
    assert empty.calls == 1


def test_invalid_range_interval_and_missing_stock(client: TestClient) -> None:
    _auth(client)
    stock = _tcs(_db())
    provider = RecordingProvider(intervals=frozenset({"1d", "15m"}))
    _use(provider, MemoryHistoryCache())
    backwards = client.get(
        f"/api/stocks/{stock.id}/history",
        params={"start_date": "2026-09-10", "end_date": "2026-09-01"},
    )
    assert backwards.status_code == 422
    intraday = client.get(
        f"/api/stocks/{stock.id}/history",
        params={"range": "1y", "interval": "15m"},
    )
    assert intraday.status_code == 422
    unknown = client.get(
        f"/api/stocks/{stock.id}/history",
        params={"start_date": "2026-09-01", "end_date": "2026-09-02", "interval": "2d"},
    )
    assert unknown.status_code == 422
    missing = client.get(f"/api/stocks/{uuid.uuid4()}/history", params={"range": "1m"})
    assert missing.status_code == 404
    assert provider.calls == 0


def test_invalid_bar_is_not_stored(client: TestClient) -> None:
    db = _db()
    stock = _tcs(db)
    provider = RecordingProvider()
    provider.get_historical_prices = lambda instrument, *, start, end, interval: _weekday_bars(start, end, interval, broken=True)  # type: ignore[method-assign]
    with pytest.raises(MarketDataError):
        get_history(
            db,
            stock.id,
            provider=provider,
            cache=MemoryHistoryCache(),
            ttl_seconds=300,
            max_years=10,
            start=date(2026, 9, 1),
            end=date(2026, 9, 2),
            today=TODAY,
        )
    count = db.scalar(select(func.count()).select_from(StockPrice).where(StockPrice.stock_id == stock.id))
    assert count == 0
    with pytest.raises(MarketDataError):
        validate_bar(_weekday_bars(date(2026, 9, 1), date(2026, 9, 1), "1d", broken=True)[0], "1d")


def test_duplicate_history_rows_are_not_inserted(client: TestClient) -> None:
    db = _db()
    stock = _tcs(db)
    provider = RecordingProvider()
    kwargs = {
        "provider": provider,
        "ttl_seconds": 300,
        "max_years": 10,
        "start": date(2026, 9, 1),
        "end": date(2026, 9, 4),
        "today": TODAY,
    }
    get_history(db, stock.id, cache=MemoryHistoryCache(), **kwargs)
    get_history(db, stock.id, cache=MemoryHistoryCache(), **kwargs)
    count = db.scalar(
        select(func.count()).select_from(StockPrice).where(StockPrice.stock_id == stock.id, StockPrice.interval == "1d")
    )
    assert count == 4
    assert provider.calls == 1


def test_redis_history_miss_then_hit(client: TestClient) -> None:
    db = _db()
    stock = _tcs(db)
    provider = RecordingProvider()
    redis = FakeRedis()
    cache = RedisHistoryCache(redis)  # type: ignore[arg-type]
    kwargs = {
        "provider": provider,
        "cache": cache,
        "ttl_seconds": 300,
        "max_years": 10,
        "start": date(2026, 9, 8),
        "end": date(2026, 9, 9),
        "today": TODAY,
    }
    first = get_history(db, stock.id, **kwargs)
    second = get_history(db, stock.id, **kwargs)
    key = history_cache_key(stock.id, "1d", date(2026, 9, 8), date(2026, 9, 9))
    assert provider.calls == 1
    assert redis.ttls[key] == 300
    assert second.fetched_at == first.fetched_at
    assert len(second.data) == len(first.data)


def test_performance_and_extremes() -> None:
    bars = [
        _stored(uuid.uuid4(), date(2026, 9, 1), close="3100", high="3200", low="2900"),
        _stored(uuid.uuid4(), date(2026, 9, 2), close="3450", high="3800", low="3000"),
    ]
    summary = performance_and_extremes(bars)
    assert summary is not None
    start_price, end_price, change, percent, high, low = summary
    assert start_price == Decimal("3100.0000")
    assert end_price == Decimal("3450.0000")
    assert change == Decimal("350.0000")
    assert percent == ((Decimal("350.0000") / Decimal("3100.0000")) * Decimal(100)).quantize(Decimal("0.0001"))
    assert high == Decimal("3800.0000")
    assert low == Decimal("2900.0000")
    assert performance_and_extremes([]) is None


def _stored(
    stock_id: uuid.UUID,
    day: date,
    *,
    close: str | None = None,
    high: str | None = None,
    low: str | None = None,
) -> StockPrice:
    price = Decimal(close) if close is not None else Decimal(3000 + day.day)
    return StockPrice(
        stock_id=stock_id,
        interval="1d",
        timestamp=datetime(day.year, day.month, day.day, 9, 15, tzinfo=IST),
        open=price - Decimal("5"),
        high=Decimal(high) if high is not None else price + Decimal("10"),
        low=Decimal(low) if low is not None else price - Decimal("8"),
        close=price,
        adjusted_close=price,
        volume=1000,
    )
