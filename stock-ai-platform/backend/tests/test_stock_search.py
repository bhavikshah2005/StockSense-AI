import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.main import app
from app.markets.profile import active_market
from app.models import Stock

PASSWORD = "Validpass1"
ORIGIN = "http://localhost:5173"


def _auth(client: TestClient) -> None:
    email = f"stocks-{uuid.uuid4().hex}@example.com"
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": PASSWORD, "full_name": "Stock Tester"},
        headers={"Origin": ORIGIN},
    )
    assert response.status_code == 201, response.text


def test_search_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/stocks/search", params={"q": "TCS"})
    assert response.status_code == 401


def test_search_symbol_returns_both_indian_exchanges(client: TestClient) -> None:
    _auth(client)
    market = active_market()
    response = client.get("/api/stocks/search", params={"q": "TCS"})
    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "TCS"
    matches = [row for row in body["results"] if row["symbol"] == "TCS"]
    assert {row["exchange"] for row in matches} == set(market.exchanges)
    row = matches[0]
    assert row["company_name"] == "Tata Consultancy Services Limited"
    assert row["currency"] == market.currency
    assert row["country"] == market.country
    assert row["country_name"] == market.country_name
    assert row["isin"] == "INE467B01029"
    assert row["sector"] == "Information Technology"


def test_search_matches_company_name_case_insensitive(client: TestClient) -> None:
    _auth(client)
    response = client.get("/api/stocks/search", params={"q": "reliance"})
    assert response.status_code == 200
    symbols = {row["symbol"] for row in response.json()["results"]}
    assert "RELIANCE" in symbols


def test_search_partial_symbol(client: TestClient) -> None:
    _auth(client)
    response = client.get("/api/stocks/search", params={"q": "HDFC"})
    assert response.status_code == 200
    assert any(row["symbol"] == "HDFCBANK" for row in response.json()["results"])


def test_search_hides_non_indian_listings(client: TestClient) -> None:
    _auth(client)
    db = _db()
    db.add(
        Stock(
            symbol="AAPL",
            company_name="Apple Inc.",
            exchange="NASDAQ",
            country="US",
            currency="USD",
            is_active=True,
        )
    )
    db.commit()
    response = client.get("/api/stocks/search", params={"q": "AAPL"})
    assert response.status_code == 200
    assert response.json()["results"] == []


def test_search_empty_query_is_rejected(client: TestClient) -> None:
    _auth(client)
    response = client.get("/api/stocks/search", params={"q": " "})
    assert response.status_code == 422


def _db() -> Session:
    override = app.dependency_overrides[get_db]
    return next(override())
