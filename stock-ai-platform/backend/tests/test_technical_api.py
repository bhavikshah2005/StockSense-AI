import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.data_providers.market_data import get_market_data_provider
from app.data_providers.market_data.india import UnconfiguredMarketDataProvider
from app.main import app
from app.markets.time import IST
from app.models import Stock, StockPrice
from app.services.technical_cache import MemoryTechnicalCache, get_technical_cache
from tests.isolation import hide_committed_market_rows

PASSWORD = "Validpass1"
ORIGIN = "http://localhost:5173"


def _auth(client: TestClient) -> None:
    response = client.post(
        "/api/auth/register",
        json={"email": f"technical-{uuid.uuid4().hex}@example.com", "password": PASSWORD, "full_name": "Technical Tester"},
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


def _use() -> MemoryTechnicalCache:
    cache = MemoryTechnicalCache()
    app.dependency_overrides[get_market_data_provider] = lambda: UnconfiguredMarketDataProvider()
    app.dependency_overrides[get_technical_cache] = lambda: cache
    return cache


def _seed(db: Session, stock: Stock, today: date) -> None:
    cursor = today
    inserted = 0
    price = 100
    while inserted < 80:
        if cursor.weekday() < 5:
            close = Decimal(price)
            db.add(
                StockPrice(
                    stock_id=stock.id,
                    interval="1d",
                    timestamp=datetime(cursor.year, cursor.month, cursor.day, 15, 30, tzinfo=IST),
                    open=close,
                    high=close + Decimal("1"),
                    low=close - Decimal("1"),
                    close=close,
                    adjusted_close=close,
                    volume=1000 + inserted,
                )
            )
            inserted += 1
            price += 1
        cursor -= timedelta(days=1)
    db.commit()


def test_technical_analysis_requires_a_session_and_known_inputs(client: TestClient) -> None:
    missing = client.get(f"/api/stocks/{uuid.uuid4()}/technical-analysis")
    assert missing.status_code == 401
    _auth(client)
    _use()
    unknown = client.get(f"/api/stocks/{uuid.uuid4()}/technical-analysis")
    assert unknown.status_code == 404
    stock = _tcs(_db())
    invalid = client.get(f"/api/stocks/{stock.id}/technical-analysis", params={"interval": "1h"})
    assert invalid.status_code == 422
    backwards = client.get(
        f"/api/stocks/{stock.id}/technical-analysis",
        params={"start_date": "2026-09-10", "end_date": "2026-09-01"},
    )
    assert backwards.status_code == 422
    empty = client.get(f"/api/stocks/{stock.id}/technical-analysis")
    assert empty.status_code == 503


def test_technical_analysis_uses_stored_bars_and_pages_patterns(client: TestClient) -> None:
    _auth(client)
    cache = _use()
    db = _db()
    stock = _tcs(db)
    today = datetime.now(UTC).astimezone(IST).date()
    _seed(db, stock, today)
    first = client.get(f"/api/stocks/{stock.id}/technical-analysis")
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["freshness"] == "current"
    assert body["indicators"]["sma_20"] is not None
    assert body["conclusion"]["category"] in {
        "bullish_evidence",
        "bearish_evidence",
        "mixed_evidence",
        "no_clear_direction",
        "insufficient_data",
    }
    lowered = first.text.lower()
    for banned in ("buy", "sell", "hold", "guarantee"):
        assert banned not in lowered
    second = client.get(f"/api/stocks/{stock.id}/technical-analysis")
    assert second.json()["calculated_at"] == body["calculated_at"]
    assert cache.get(next(iter(cache._values))) is not None
    history = client.get(f"/api/stocks/{stock.id}/technical-analysis/patterns", params={"limit": 1, "status": "developing"})
    assert history.status_code == 200, history.text
    assert history.json()["limit"] == 1
    assert history.json()["total"] >= 0
    bad_status = client.get(f"/api/stocks/{stock.id}/technical-analysis/patterns", params={"status": "buy"})
    assert bad_status.status_code == 422
    summary = client.get(f"/api/stocks/{stock.id}/technical-analysis/summary")
    assert summary.status_code == 200
    assert summary.json()["conclusion"]["category"] == body["conclusion"]["category"]
    assert "not a forecast" in summary.json()["conclusion"]["text"]
