import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.data_providers.market_data import get_market_data_provider
from app.data_providers.market_data.base import InstrumentRef, MarketDataProvider, MarketStatus, PriceBar, Quote
from app.data_providers.market_data.errors import RATE_LIMITED, UNAUTHORIZED, MarketDataError
from app.data_providers.market_data.india import IndianMarketDataProvider, UnconfiguredMarketDataProvider
from app.data_providers.market_data.normalize import normalize_bar, normalize_quote
from app.main import app
from app.markets.time import IST, to_ist
from app.models import Stock, StockPrice
from app.services.market_data_service import get_quote, sync_historical_prices
from app.services.market_validation import validate_bar, validate_quote
from app.services.quote_cache import MemoryQuoteCache, RedisQuoteCache, get_quote_cache
from tests.isolation import hide_committed_market_rows

PASSWORD = "Validpass1"
ORIGIN = "http://localhost:5173"


class ScriptedProvider(MarketDataProvider):
    def __init__(
        self,
        quote: Quote | None = None,
        error: Exception | None = None,
        bars: list[PriceBar] | None = None,
        intervals: frozenset[str] = frozenset({"1d"}),
    ) -> None:
        self.quote = quote
        self.error = error
        self.bars = bars or []
        self._intervals = intervals
        self.calls = 0

    @property
    def name(self) -> str:
        return "scripted"

    @property
    def supported_intervals(self) -> frozenset[str]:
        return self._intervals

    def get_quote(self, instrument: InstrumentRef) -> Quote:
        self.calls += 1
        if self.error is not None:
            raise self.error
        assert self.quote is not None
        return self.quote

    def get_historical_prices(
        self,
        instrument: InstrumentRef,
        *,
        start: date,
        end: date,
        interval: str,
    ) -> list[PriceBar]:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.bars

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
    email = f"quotes-{uuid.uuid4().hex}@example.com"
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": PASSWORD, "full_name": "Quote Tester"},
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


def _quote_for(stock: Stock, *, current: str = "3452.5000", previous: str = "3418.2000") -> Quote:
    return Quote(
        symbol=stock.symbol,
        exchange=stock.exchange,
        currency=stock.currency,
        current_price=Decimal(current),
        previous_close=Decimal(previous),
        change=None,
        change_percent=None,
        open=Decimal("3420.0000"),
        high=Decimal("3465.0000"),
        low=Decimal("3410.0000"),
        volume=1234567,
        market_timestamp=datetime(2026, 9, 23, 5, 1, tzinfo=UTC),
        delayed=True,
        delay_minutes=15,
    )


def _bar(close: str = "3452.5000") -> PriceBar:
    return PriceBar(
        timestamp=datetime(2026, 9, 23, 9, 15, tzinfo=IST),
        interval="1d",
        open=Decimal("3420.0000"),
        high=Decimal("3465.0000"),
        low=Decimal("3410.0000"),
        close=Decimal(close),
        adjusted_close=Decimal(close),
        volume=1000,
    )


def _use_provider(provider: MarketDataProvider, cache: MemoryQuoteCache | RedisQuoteCache | None = None) -> None:
    app.dependency_overrides[get_market_data_provider] = lambda: provider
    if cache is not None:
        app.dependency_overrides[get_quote_cache] = lambda: cache


def test_quote_requires_authentication(client: TestClient) -> None:
    response = client.get(f"/api/stocks/{uuid.uuid4()}/quote")
    assert response.status_code == 401


def test_unconfigured_provider_returns_service_error(client: TestClient) -> None:
    _auth(client)
    stock = _tcs(_db())
    _use_provider(UnconfiguredMarketDataProvider(), MemoryQuoteCache())
    response = client.get(f"/api/stocks/{stock.id}/quote")
    assert response.status_code == 503
    assert response.json()["detail"] == "Market data service temporarily unavailable"
    assert "current_price" not in response.text
    assert "MARKET_DATA_API_KEY" not in response.text


def test_valid_quote_normalizes_change_and_keeps_timestamps(client: TestClient) -> None:
    _auth(client)
    stock = _tcs(_db())
    provider = ScriptedProvider(_quote_for(stock))
    _use_provider(provider, MemoryQuoteCache())
    response = client.get(f"/api/stocks/{stock.id}/quote")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["symbol"] == "TCS"
    assert body["exchange"] == "NSE"
    assert body["currency"] == "INR"
    assert body["current_price"] == "3452.5000"
    assert body["previous_close"] == "3418.2000"
    assert body["change"] == "34.3000"
    assert body["open"] == "3420.0000"
    assert body["high"] == "3465.0000"
    assert body["low"] == "3410.0000"
    assert body["volume"] == 1234567
    assert body["delayed"] is True
    assert body["delay_minutes"] == 15
    assert body["market_timestamp"] != body["fetched_at"]
    assert Decimal(body["change_percent"]) == (
        (Decimal("34.3000") / Decimal("3418.2000")) * Decimal(100)
    ).quantize(Decimal("0.0001"))
    assert "api_key" not in response.text


def test_negative_move_is_signed() -> None:
    source = _quote_for(
        Stock(symbol="TCS", exchange="NSE", currency="INR", country="IN", company_name="TCS"),
        current="3400.0000",
        previous="3418.2000",
    )
    quote = Quote(
        symbol=source.symbol,
        exchange=source.exchange,
        currency=source.currency,
        current_price=source.current_price,
        previous_close=source.previous_close,
        change=None,
        change_percent=None,
        open=Decimal("3410.0000"),
        high=source.high,
        low=Decimal("3390.0000"),
        volume=source.volume,
        market_timestamp=source.market_timestamp,
        delayed=source.delayed,
        delay_minutes=source.delay_minutes,
    )
    checked = validate_quote(quote, InstrumentRef("TCS", "NSE", "INR", "IN"))
    assert checked.change == Decimal("-18.2000")
    assert checked.change_percent is not None
    assert checked.change_percent < 0


def test_invalid_provider_response_is_rejected(client: TestClient) -> None:
    _auth(client)
    stock = _tcs(_db())
    broken = _quote_for(stock)
    broken = Quote(
        symbol=broken.symbol,
        exchange=broken.exchange,
        currency=broken.currency,
        current_price=Decimal("-1"),
        previous_close=broken.previous_close,
        change=None,
        change_percent=None,
        open=broken.open,
        high=broken.high,
        low=broken.low,
        volume=broken.volume,
        market_timestamp=broken.market_timestamp,
        delayed=False,
        delay_minutes=None,
    )
    _use_provider(ScriptedProvider(broken), MemoryQuoteCache())
    response = client.get(f"/api/stocks/{stock.id}/quote")
    assert response.status_code == 502
    assert response.json()["detail"] == "Market data provider unavailable"


def test_provider_timeout_hides_internal_detail(client: TestClient) -> None:
    _auth(client)
    stock = _tcs(_db())
    _use_provider(
        ScriptedProvider(error=TimeoutError("timed out at https://vendor.example/secret-key")),
        MemoryQuoteCache(),
    )
    response = client.get(f"/api/stocks/{stock.id}/quote")
    assert response.status_code == 502
    assert response.json()["detail"] == "Market data provider unavailable"
    assert "secret-key" not in response.text


def test_provider_rate_limit(client: TestClient) -> None:
    _auth(client)
    stock = _tcs(_db())
    _use_provider(ScriptedProvider(error=MarketDataError(RATE_LIMITED)), MemoryQuoteCache())
    response = client.get(f"/api/stocks/{stock.id}/quote")
    assert response.status_code == 429
    assert response.json()["detail"] == "Market data rate limit reached"


def test_provider_authentication_failure(client: TestClient) -> None:
    _auth(client)
    stock = _tcs(_db())
    _use_provider(ScriptedProvider(error=MarketDataError(UNAUTHORIZED)), MemoryQuoteCache())
    response = client.get(f"/api/stocks/{stock.id}/quote")
    assert response.status_code == 502
    assert response.json()["detail"] == "Market data provider unavailable"


def test_stock_not_found(client: TestClient) -> None:
    _auth(client)
    response = client.get(f"/api/stocks/{uuid.uuid4()}/quote")
    assert response.status_code == 404
    assert response.json()["detail"] == "Stock not found"


def test_normalization_uses_decimal_and_rejects_naive_time() -> None:
    instrument = InstrumentRef("TCS", "NSE", "INR", "IN")
    quote = normalize_quote(
        {
            "symbol": "TCS",
            "exchange": "NSE",
            "currency": "INR",
            "current_price": "3452.50",
            "previous_close": "3418.20",
            "change": None,
            "change_percent": None,
            "open": "3420",
            "high": "3465",
            "low": "3410",
            "volume": "1234567",
            "market_timestamp": "2026-09-23T05:01:00+00:00",
            "delayed": False,
            "delay_minutes": None,
        },
        instrument,
    )
    assert isinstance(quote.current_price, Decimal)
    assert quote.current_price == Decimal("3452.5000")
    assert quote.market_timestamp.tzinfo is not None
    with pytest.raises(MarketDataError):
        normalize_quote(
            {
                "symbol": "TCS",
                "exchange": "NSE",
                "currency": "INR",
                "current_price": "1",
                "market_timestamp": "2026-09-23T10:31:00",
                "delayed": False,
            },
            instrument,
        )


def test_price_validation_rejects_bad_ohlc() -> None:
    instrument = InstrumentRef("TCS", "NSE", "INR", "IN")
    quote = _quote_for(Stock(symbol="TCS", exchange="NSE", currency="INR", country="IN", company_name="TCS"))
    with pytest.raises(MarketDataError):
        validate_quote(
            Quote(
                symbol=quote.symbol,
                exchange=quote.exchange,
                currency=quote.currency,
                current_price=quote.current_price,
                previous_close=quote.previous_close,
                change=None,
                change_percent=None,
                open=quote.open,
                high=Decimal("3400"),
                low=Decimal("3465"),
                volume=quote.volume,
                market_timestamp=quote.market_timestamp,
                delayed=False,
                delay_minutes=None,
            ),
            instrument,
        )
    with pytest.raises(MarketDataError):
        validate_bar(
            PriceBar(
                timestamp=datetime(2026, 9, 23, 9, 15, tzinfo=IST),
                interval="1d",
                open=Decimal("10"),
                high=Decimal("9"),
                low=Decimal("11"),
                close=Decimal("10"),
                adjusted_close=None,
                volume=-1,
            ),
            "1d",
        )


def test_duplicate_historical_rows_upsert(client: TestClient) -> None:
    db = _db()
    stock = _tcs(db)
    provider = ScriptedProvider(bars=[_bar("3452.5000")])
    stored = sync_historical_prices(
        db,
        stock.id,
        provider=provider,
        interval="1d",
        start=date(2026, 9, 23),
        end=date(2026, 9, 23),
    )
    assert stored == 1
    provider.bars = [_bar("3460.0000")]
    sync_historical_prices(
        db,
        stock.id,
        provider=provider,
        interval="1d",
        start=date(2026, 9, 23),
        end=date(2026, 9, 23),
    )
    count = db.scalar(
        select(func.count()).select_from(StockPrice).where(StockPrice.stock_id == stock.id, StockPrice.interval == "1d")
    )
    assert count == 1
    row = db.scalar(select(StockPrice).where(StockPrice.stock_id == stock.id))
    assert row is not None
    assert row.close == Decimal("3460.0000")
    assert row.timestamp.tzinfo is not None
    assert row.timestamp.astimezone(IST).hour == 9
    _auth(client)
    response = client.get(f"/api/stocks/{stock.id}/prices", params={"interval": "1d"})
    assert response.status_code == 200
    body = response.json()
    assert len(body["bars"]) == 1
    assert body["bars"][0]["close"] == "3460.0000"
    assert body["bars"][0]["volume"] == 1000


def test_first_sync_without_start_does_not_call_provider(client: TestClient) -> None:
    db = _db()
    stock = _tcs(db)
    provider = ScriptedProvider(bars=[_bar()])
    with pytest.raises(MarketDataError) as caught:
        sync_historical_prices(db, stock.id, provider=provider, interval="1d", start=None, end=None)
    assert caught.value.code == "invalid_range"
    assert provider.calls == 0


def test_redis_cache_miss_then_hit(client: TestClient) -> None:
    connection_db = _db()
    stock = _tcs(connection_db)
    provider = ScriptedProvider(_quote_for(stock))
    redis = FakeRedis()
    cache = RedisQuoteCache(redis)  # type: ignore[arg-type]
    first = get_quote(connection_db, stock.id, provider=provider, cache=cache, ttl_seconds=15)
    assert provider.calls == 1
    assert redis.ttls[f"market:quote:{stock.id}"] == 15
    second = get_quote(connection_db, stock.id, provider=provider, cache=cache, ttl_seconds=15)
    assert provider.calls == 1
    assert second.fetched_at == first.fetched_at
    assert second.market_timestamp != second.fetched_at


def test_memory_cache_miss_calls_provider_once(client: TestClient) -> None:
    _auth(client)
    stock = _tcs(_db())
    provider = ScriptedProvider(_quote_for(stock))
    _use_provider(provider, MemoryQuoteCache())
    first = client.get(f"/api/stocks/{stock.id}/quote")
    second = client.get(f"/api/stocks/{stock.id}/quote")
    assert first.status_code == 200
    assert second.status_code == 200
    assert provider.calls == 1
    assert first.json()["fetched_at"] == second.json()["fetched_at"]


def test_ist_conversion() -> None:
    utc = datetime(2026, 9, 23, 5, 1, tzinfo=UTC)
    ist = to_ist(utc)
    assert ist.hour == 10
    assert ist.minute == 31
    assert ist.tzinfo == IST
    with pytest.raises(ValueError):
        to_ist(datetime(2026, 9, 23, 10, 31))


def test_unsupported_exchange(client: TestClient) -> None:
    _auth(client)
    db = _db()
    foreign = Stock(
        symbol="AAPL",
        company_name="Apple Inc.",
        exchange="NASDAQ",
        country="US",
        currency="USD",
        is_active=True,
    )
    db.add(foreign)
    db.commit()
    response = client.get(f"/api/stocks/{foreign.id}/quote")
    assert response.status_code == 422
    assert response.json()["detail"] == "Exchange is not supported"


def test_indian_placeholder_does_not_call_a_vendor() -> None:
    provider = IndianMarketDataProvider("example-vendor")
    with pytest.raises(MarketDataError) as caught:
        provider.get_quote(InstrumentRef("TCS", "NSE", "INR", "IN"))
    assert caught.value.code == "not_configured"
    assert provider.supported_intervals == frozenset()
    bar = normalize_bar(
        {
            "timestamp": "2026-09-23T03:45:00+00:00",
            "interval": "1d",
            "open": "1.0000",
            "high": "2.0000",
            "low": "1.0000",
            "close": "1.5000",
            "adjusted_close": None,
            "volume": 10,
        }
    )
    assert bar.timestamp.astimezone(IST).hour == 9


def test_market_status_is_unavailable_without_a_source(client: TestClient) -> None:
    _auth(client)
    app.dependency_overrides[get_market_data_provider] = lambda: UnconfiguredMarketDataProvider()
    response = client.get("/api/markets/NSE/status")
    assert response.status_code == 503
    assert response.json()["detail"] == "Market data service temporarily unavailable"
    assert "open" not in response.json()["detail"]
