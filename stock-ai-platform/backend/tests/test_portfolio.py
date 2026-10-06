"""Portfolio ledger, valuation gaps, and hypothetical position size. Quotes are fixtures."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.data_providers.market_data.errors import MarketDataError
from app.main import app
from app.models import PortfolioHolding, Stock, StockPrice, User
from app.portfolio.accounting import CashMove, Trade, replay
from app.portfolio.sizing import SizingError, size_position
from app.schemas.market_data import QuoteResponse
from app.services.portfolio_service import add_cash, add_transaction, delete_transaction, update_transaction, valuation
from tests.isolation import hide_committed_market_rows

PASSWORD = "Validpass1"
ORIGIN = "http://localhost:5173"
WHEN = datetime(2026, 9, 24, 4, 0, tzinfo=UTC)


def _auth(client: TestClient, prefix: str = "portfolio") -> str:
    email = f"{prefix}-{uuid.uuid4().hex}@example.com"
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": PASSWORD, "full_name": "Portfolio Tester"},
        headers={"Origin": ORIGIN},
    )
    assert response.status_code == 201, response.text
    return email


def _db() -> Session:
    return next(app.dependency_overrides[get_db]())


def _user(db: Session, email: str) -> User:
    user = db.scalar(select(User).where(User.email == email))
    assert user is not None
    return user


def _tcs(db: Session) -> Stock:
    stock = db.scalar(select(Stock).where(Stock.symbol == "TCS", Stock.exchange == "NSE"))
    assert stock is not None
    hide_committed_market_rows(db, stock.id)
    return stock


def _quote(stock: Stock, price: str, timestamp: datetime, delayed: bool = True) -> QuoteResponse:
    return QuoteResponse(
        stock_id=stock.id,
        symbol=stock.symbol,
        exchange=stock.exchange,
        currency="INR",
        current_price=Decimal(price),
        previous_close=None,
        change=None,
        change_percent=None,
        open=None,
        high=None,
        low=None,
        volume=None,
        market_timestamp=timestamp,
        fetched_at=timestamp,
        delayed=delayed,
        delay_minutes=None,
    )


def test_weighted_average_includes_charges_and_partial_sells() -> None:
    buy = Trade("b", "TCS", "buy", Decimal("10"), Decimal("100"), Decimal("20"), WHEN)
    sell = Trade("s", "TCS", "sell", Decimal("4"), Decimal("110"), Decimal("10"), WHEN + timedelta(hours=1))
    ledger = replay([buy, sell], [CashMove("d", "deposit", Decimal("2000"), WHEN - timedelta(hours=1))])
    position = ledger.positions["TCS"]
    assert position.quantity == Decimal("6")
    assert position.cost == Decimal("612.00")
    assert position.realized == Decimal("22.00")
    assert ledger.cash == Decimal("2000.00") - Decimal("1020.00") + Decimal("430.00")


def test_sell_cannot_exceed_shares_or_spend_unfunded_cash() -> None:
    try:
        replay([Trade("s", "TCS", "sell", Decimal("1"), Decimal("10"), Decimal("0"), WHEN)], [])
    except Exception as exc:
        assert exc.code == "insufficient_shares"
    else:
        raise AssertionError("expected rejection")
    try:
        replay([Trade("b", "TCS", "buy", Decimal("1"), Decimal("10"), Decimal("0"), WHEN)], [])
    except Exception as exc:
        assert exc.code == "insufficient_cash"
    else:
        raise AssertionError("expected rejection")


def test_position_size_uses_the_tightest_limit() -> None:
    risk = size_position(
        capital=Decimal("100000"),
        entry=Decimal("100"),
        stop=Decimal("90"),
        max_risk_inr=Decimal("250"),
        max_risk_percent=None,
        max_allocation_percent=Decimal("50"),
        max_shares=100,
    )
    assert risk.quantity == 25
    assert risk.binding_constraint == "risk"
    assert risk.per_share_risk == Decimal("10.00")
    capital = size_position(
        capital=Decimal("1000"),
        entry=Decimal("400"),
        stop=Decimal("300"),
        max_risk_inr=Decimal("5000"),
        max_risk_percent=None,
        max_allocation_percent=None,
        max_shares=None,
    )
    assert capital.quantity == 2
    assert capital.binding_constraint == "capital"
    try:
        size_position(
            capital=Decimal("1000"),
            entry=Decimal("100"),
            stop=Decimal("100"),
            max_risk_inr=Decimal("50"),
            max_risk_percent=None,
            max_allocation_percent=None,
            max_shares=None,
        )
    except SizingError as exc:
        assert exc.code == "invalid_stop"
    else:
        raise AssertionError("expected rejection")
    try:
        size_position(
            capital=Decimal("100"),
            entry=Decimal("80"),
            stop=Decimal("79"),
            max_risk_inr=Decimal("0.10"),
            max_risk_percent=None,
            max_allocation_percent=None,
            max_shares=None,
        )
    except SizingError as exc:
        assert exc.code == "below_one_share"
    else:
        raise AssertionError("expected rejection")


def test_transactions_recalculate_and_stay_private(client: TestClient, monkeypatch) -> None:
    email = _auth(client)
    other = None
    db = _db()
    user = _user(db, email)
    stock = _tcs(db)
    created = client.post("/api/portfolios", json={"name": "Main book", "description": "Test fixture"})
    assert created.status_code == 201, created.text
    portfolio_id = created.json()["id"]
    assert created.json()["currency"] == "INR"
    assert Decimal(created.json()["cash"]) == 0
    deposit = client.post(
        f"/api/portfolios/{portfolio_id}/cash",
        json={"kind": "deposit", "amount": "5000", "occurred_at": "2026-09-20T04:00:00Z"},
    )
    assert deposit.status_code == 201, deposit.text
    bought = add_transaction(
        db,
        user,
        uuid.UUID(portfolio_id),
        stock_id=stock.id,
        side="buy",
        quantity=Decimal("10"),
        price=Decimal("100"),
        charges=Decimal("20"),
        traded_at=WHEN,
        note=None,
    )
    holding = db.scalar(select(PortfolioHolding).where(PortfolioHolding.portfolio_id == uuid.UUID(portfolio_id)))
    assert holding is not None
    assert holding.quantity == Decimal("10")
    assert holding.cost_basis == Decimal("1020.00")
    update_transaction(
        db,
        user,
        uuid.UUID(portfolio_id),
        bought.id,
        quantity=Decimal("8"),
        price=Decimal("100"),
        charges=Decimal("0"),
        traded_at=WHEN,
        note=None,
    )
    db.expire_all()
    holding = db.scalar(select(PortfolioHolding).where(PortfolioHolding.portfolio_id == uuid.UUID(portfolio_id)))
    assert holding is not None
    assert holding.cost_basis == Decimal("800.00")
    sold = add_transaction(
        db,
        user,
        uuid.UUID(portfolio_id),
        stock_id=stock.id,
        side="sell",
        quantity=Decimal("3"),
        price=Decimal("110"),
        charges=Decimal("0"),
        traded_at=WHEN + timedelta(hours=6),
        note=None,
    )
    db.expire_all()
    holding = db.scalar(select(PortfolioHolding).where(PortfolioHolding.portfolio_id == uuid.UUID(portfolio_id)))
    assert holding is not None
    assert holding.quantity == Decimal("5")
    oversized = client.post(
        f"/api/portfolios/{portfolio_id}/transactions",
        json={"stock_id": str(stock.id), "side": "sell", "quantity": "9", "price": "100", "charges": "0", "traded_at": "2026-09-23T04:00:00Z"},
    )
    assert oversized.status_code == 422
    delete_transaction(db, user, uuid.UUID(portfolio_id), sold.id)
    db.expire_all()
    holding = db.scalar(select(PortfolioHolding).where(PortfolioHolding.portfolio_id == uuid.UUID(portfolio_id)))
    assert holding is not None
    assert holding.quantity == Decimal("8")

    def missing(*args, **kwargs):
        del args, kwargs
        raise MarketDataError("unavailable")

    monkeypatch.setattr("app.services.portfolio_service.get_quote", missing)
    body = valuation(db, user, uuid.UUID(portfolio_id), provider=None, cache=None, ttl_seconds=15, now=WHEN + timedelta(days=2))  # type: ignore[arg-type]
    assert body["valuation_complete"] is False
    assert body["holdings"][0]["price_state"] == "unavailable"
    assert body["market_value"] is None

    def stale(*args, **kwargs):
        del args, kwargs
        return _quote(stock, "150", WHEN - timedelta(days=30))

    monkeypatch.setattr("app.services.portfolio_service.get_quote", stale)
    stale_body = valuation(db, user, uuid.UUID(portfolio_id), provider=None, cache=None, ttl_seconds=15, now=WHEN + timedelta(days=2))  # type: ignore[arg-type]
    assert stale_body["holdings"][0]["price_state"] == "stale"
    assert stale_body["holdings"][0]["last_price"] == Decimal("150")
    assert stale_body["market_value"] is None

    def current(*args, **kwargs):
        del args, kwargs
        return _quote(stock, "120", WHEN + timedelta(days=1))

    monkeypatch.setattr("app.services.portfolio_service.get_quote", current)
    fresh = valuation(db, user, uuid.UUID(portfolio_id), provider=None, cache=None, ttl_seconds=15, now=WHEN + timedelta(days=2))  # type: ignore[arg-type]
    assert fresh["valuation_complete"] is True
    assert fresh["market_value"] == Decimal("960.00")
    assert fresh["unrealized_pnl"] == Decimal("160.00")
    client.post("/api/auth/logout")
    _auth(client, "other")
    other = client.get(f"/api/portfolios/{portfolio_id}")
    assert other.status_code == 404
    hidden = client.get(f"/api/portfolios/{portfolio_id}/transactions")
    assert hidden.status_code == 404


def test_history_requires_stored_closes_and_size_endpoint_rejects_a_stop(client: TestClient) -> None:
    _auth(client)
    db = _db()
    stock = _tcs(db)
    created = client.post("/api/portfolios", json={"name": "History book", "description": None})
    portfolio_id = created.json()["id"]
    client.post(f"/api/portfolios/{portfolio_id}/cash", json={"kind": "deposit", "amount": "1000", "occurred_at": "2026-09-24T03:30:00Z"})
    trade = client.post(
        f"/api/portfolios/{portfolio_id}/transactions",
        json={"stock_id": str(stock.id), "side": "buy", "quantity": "2", "price": "100", "charges": "0", "traded_at": "2026-09-24T04:00:00Z"},
    )
    assert trade.status_code == 201, trade.text
    missing = client.get(f"/api/portfolios/{portfolio_id}/history")
    assert missing.json()["status"] == "insufficient_data"
    db.add(
        StockPrice(
            stock_id=stock.id,
            interval="1d",
            timestamp=WHEN,
            open=Decimal("100"),
            high=Decimal("101"),
            low=Decimal("99"),
            close=Decimal("100"),
            adjusted_close=None,
            volume=1,
        )
    )
    db.commit()
    covered = client.get(f"/api/portfolios/{portfolio_id}/history")
    assert covered.json()["status"] == "complete"
    assert covered.json()["points"][0]["holdings_value"] == "200.00"
    rejected = client.post(
        "/api/portfolios/position-size",
        json={"capital": "10000", "entry": "100", "stop": "120", "max_risk_inr": "500"},
    )
    assert rejected.status_code == 422
    sized = client.post(
        "/api/portfolios/position-size",
        json={"capital": "10000", "entry": "100", "stop": "90", "max_risk_inr": "250", "max_shares": 10},
    )
    assert sized.status_code == 200, sized.text
    assert sized.json()["quantity"] == 10
    assert sized.json()["binding_constraint"] == "share_cap"
    assert "not a trade instruction" in sized.json()["warning"]
