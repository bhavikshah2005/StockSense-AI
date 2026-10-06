import uuid
from datetime import UTC, datetime
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.data_providers.market_data import get_market_data_provider
from app.data_providers.market_data.base import InstrumentRef, MarketDataProvider, MarketStatus, PriceBar, Quote
from app.data_providers.market_data.india import UnconfiguredMarketDataProvider
from app.main import app
from app.models import Stock, StockPrice

PASSWORD = "Validpass1"
ORIGIN = "http://localhost:5173"


class OneQuote(MarketDataProvider):
    def __init__(self, price: str) -> None:
        self.price = Decimal(price)

    @property
    def name(self) -> str:
        return "one-quote"

    @property
    def supported_intervals(self) -> frozenset[str]:
        return frozenset({"1d"})

    def get_quote(self, instrument: InstrumentRef) -> Quote:
        return Quote(
            symbol=instrument.symbol,
            exchange=instrument.exchange,
            currency=instrument.currency,
            current_price=self.price,
            previous_close=Decimal("100"),
            change=None,
            change_percent=None,
            open=None,
            high=None,
            low=None,
            volume=10,
            market_timestamp=datetime(2026, 9, 24, 9, 45, tzinfo=UTC),
            delayed=True,
            delay_minutes=None,
        )

    def get_historical_prices(self, instrument: InstrumentRef, *, start, end, interval: str) -> list[PriceBar]:
        del instrument, start, end, interval
        return []

    def get_market_status(self, exchange: str) -> MarketStatus:
        raise NotImplementedError


def _auth(client: TestClient, email: str | None = None) -> str:
    address = email or f"watch-{uuid.uuid4().hex}@example.com"
    response = client.post(
        "/api/auth/register",
        json={"email": address, "password": PASSWORD, "full_name": "Watch Tester"},
        headers={"Origin": ORIGIN},
    )
    assert response.status_code == 201, response.text
    return address


def _login(client: TestClient, email: str) -> None:
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": PASSWORD},
        headers={"Origin": ORIGIN},
    )
    assert response.status_code == 200, response.text


def _db() -> Session:
    return next(app.dependency_overrides[get_db]())


def _tcs(db: Session) -> Stock:
    stock = db.scalar(select(Stock).where(Stock.symbol == "TCS", Stock.exchange == "NSE"))
    assert stock is not None
    return stock


def _use(provider: MarketDataProvider | None = None) -> None:
    app.dependency_overrides[get_market_data_provider] = lambda: provider or UnconfiguredMarketDataProvider()


def test_watchlist_crud_membership_order_and_default(client: TestClient) -> None:
    _use()
    email = _auth(client)
    created = client.post("/api/watchlists", json={"name": "  Core  ", "description": "  Daily names  "})
    assert created.status_code == 201, created.text
    first = created.json()
    assert first["name"] == "Core"
    assert first["is_default"] is True
    assert first["description"] == "Daily names"
    second = client.post("/api/watchlists", json={"name": "Ideas"})
    assert second.status_code == 201, second.text
    assert second.json()["is_default"] is False
    duplicate = client.post("/api/watchlists", json={"name": "core"})
    assert duplicate.status_code == 409
    blank = client.post("/api/watchlists", json={"name": "   "})
    assert blank.status_code == 422
    long_name = client.post("/api/watchlists", json={"name": "A" * (settings.watchlist_name_max_length + 1)})
    assert long_name.status_code == 422

    listing = client.get("/api/watchlists")
    assert listing.status_code == 200
    assert [item["name"] for item in listing.json()["results"]] == ["Core", "Ideas"]

    stock = _tcs(_db())
    missing_stock = client.post(f"/api/watchlists/{first['id']}/stocks", json={"stock_id": str(uuid.uuid4())})
    assert missing_stock.status_code == 404
    added = client.post(f"/api/watchlists/{first['id']}/stocks", json={"stock_id": str(stock.id)})
    assert added.status_code == 200, added.text
    assert added.json()["stocks"][0]["symbol"] == "TCS"
    assert added.json()["stocks"][0]["quote"]["available"] is False
    again = client.post(f"/api/watchlists/{first['id']}/stocks", json={"stock_id": str(stock.id)})
    assert again.status_code == 409

    other = db_other = _db().scalar(select(Stock).where(Stock.symbol == "INFY", Stock.exchange == "NSE"))
    assert other is not None
    del db_other
    both = client.post(f"/api/watchlists/{first['id']}/stocks", json={"stock_id": str(other.id)})
    assert both.status_code == 200, both.text
    ids = [item["stock_id"] for item in both.json()["stocks"]]
    assert ids == [str(stock.id), str(other.id)]
    flipped = client.patch(f"/api/watchlists/{first['id']}/stocks/order", json={"stock_ids": list(reversed(ids))})
    assert flipped.status_code == 200, flipped.text
    assert [item["stock_id"] for item in flipped.json()["stocks"]] == list(reversed(ids))
    partial = client.patch(f"/api/watchlists/{first['id']}/stocks/order", json={"stock_ids": [ids[0]]})
    assert partial.status_code == 422

    renamed = client.patch(f"/api/watchlists/{first['id']}", json={"name": "Primary"})
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Primary"
    chosen = client.patch(f"/api/watchlists/{second.json()['id']}/default")
    assert chosen.status_code == 200
    assert chosen.json()["is_default"] is True
    lists = client.get("/api/watchlists").json()["results"]
    assert sum(1 for item in lists if item["is_default"]) == 1

    client.post("/api/auth/logout", headers={"Origin": ORIGIN})
    _login(client, email)
    restored = client.get(f"/api/watchlists/{first['id']}")
    assert restored.status_code == 200
    assert [item["symbol"] for item in restored.json()["stocks"]] == ["INFY", "TCS"]

    before = _db().scalar(select(func.count()).select_from(Stock).where(Stock.id == stock.id))
    removed = client.delete(f"/api/watchlists/{first['id']}/stocks/{stock.id}")
    assert removed.status_code == 204
    deleted = client.delete(f"/api/watchlists/{first['id']}")
    assert deleted.status_code == 204
    after = _db().scalar(select(func.count()).select_from(Stock).where(Stock.id == stock.id))
    assert before == after == 1
    gone = client.get(f"/api/watchlists/{first['id']}")
    assert gone.status_code == 404


def test_watchlist_is_private_to_the_owner(client: TestClient) -> None:
    _use()
    _auth(client)
    created = client.post("/api/watchlists", json={"name": "Private"})
    watchlist_id = created.json()["id"]
    stock = _tcs(_db())
    client.post(f"/api/watchlists/{watchlist_id}/stocks", json={"stock_id": str(stock.id)})
    _auth(client)
    for response in (
        client.get(f"/api/watchlists/{watchlist_id}"),
        client.patch(f"/api/watchlists/{watchlist_id}", json={"name": "Stolen"}),
        client.delete(f"/api/watchlists/{watchlist_id}"),
        client.post(f"/api/watchlists/{watchlist_id}/stocks", json={"stock_id": str(stock.id)}),
        client.delete(f"/api/watchlists/{watchlist_id}/stocks/{stock.id}"),
        client.patch(f"/api/watchlists/{watchlist_id}/stocks/order", json={"stock_ids": [str(stock.id)]}),
        client.patch(f"/api/watchlists/{watchlist_id}/default"),
    ):
        assert response.status_code == 404, response.text
    anonymous = client.get("/api/watchlists")
    client.post("/api/auth/logout", headers={"Origin": ORIGIN})
    assert client.get("/api/watchlists").status_code == 401
    del anonymous


def test_watchlist_limits_and_real_quote(client: TestClient) -> None:
    _use(OneQuote("2100.50"))
    _auth(client)
    original_lists = settings.watchlist_max_lists
    original_stocks = settings.watchlist_max_stocks
    settings.watchlist_max_lists = 1
    settings.watchlist_max_stocks = 1
    try:
        first = client.post("/api/watchlists", json={"name": "Only"})
        assert first.status_code == 201
        blocked = client.post("/api/watchlists", json={"name": "Second"})
        assert blocked.status_code == 422
        stock = _tcs(_db())
        added = client.post(f"/api/watchlists/{first.json()['id']}/stocks", json={"stock_id": str(stock.id)})
        assert added.status_code == 200, added.text
        quote = added.json()["stocks"][0]["quote"]
        assert quote["available"] is True
        assert quote["delayed"] is True
        assert quote["source"] == "one-quote"
        assert quote["current_price"] == "2100.50"
        other = _db().scalar(select(Stock).where(Stock.symbol == "INFY", Stock.exchange == "NSE"))
        assert other is not None
        full = client.post(f"/api/watchlists/{first.json()['id']}/stocks", json={"stock_id": str(other.id)})
        assert full.status_code == 422
    finally:
        settings.watchlist_max_lists = original_lists
        settings.watchlist_max_stocks = original_stocks


def test_prices_remain_when_a_watchlist_is_deleted(client: TestClient) -> None:
    _use()
    _auth(client)
    created = client.post("/api/watchlists", json={"name": "Temp"})
    stock = _tcs(_db())
    before = _db().scalar(select(func.count()).select_from(StockPrice).where(StockPrice.stock_id == stock.id))
    client.post(f"/api/watchlists/{created.json()['id']}/stocks", json={"stock_id": str(stock.id)})
    assert client.delete(f"/api/watchlists/{created.json()['id']}").status_code == 204
    after = _db().scalar(select(func.count()).select_from(StockPrice).where(StockPrice.stock_id == stock.id))
    assert before == after
