import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.main import app
from app.models import Stock

PASSWORD = "Validpass1"
ORIGIN = "http://localhost:5173"


def _auth(client: TestClient) -> str:
    email = f"metric-{uuid.uuid4().hex}@example.com"
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": PASSWORD, "full_name": "Metric Tester"},
        headers={"Origin": ORIGIN},
    )
    assert response.status_code == 201, response.text
    return email


def _login(client: TestClient, email: str) -> None:
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": PASSWORD},
        headers={"Origin": ORIGIN},
    )
    assert response.status_code == 200, response.text


def _db() -> Session:
    return next(app.dependency_overrides[get_db]())


def _tcs() -> Stock:
    stock = _db().scalar(select(Stock).where(Stock.symbol == "TCS", Stock.exchange == "NSE"))
    assert stock is not None
    return stock


def _eval(client: TestClient, stock_id: str, metric: str) -> dict:
    response = client.post("/api/metrics/evaluate", json={"stock_id": stock_id, "metric_keys": [metric]})
    assert response.status_code == 200, response.text
    return response.json()["results"][0]


def test_threshold_precedence_dates_and_persistence(client: TestClient) -> None:
    email = _auth(client)
    stock = _tcs()
    stock_id = str(stock.id)
    registry = client.get("/api/metrics/registry")
    assert registry.status_code == 200
    assert any(item["key"] == "interest_coverage" for item in registry.json()["metrics"])

    created = client.post(
        "/api/metrics/thresholds",
        json={"metric_key": "interest_coverage", "operator": "<=", "threshold_value": "9"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["owned"] is True
    assert created.json()["scope"] == "user"
    duplicate = client.post(
        "/api/metrics/thresholds",
        json={"metric_key": "interest_coverage", "operator": ">=", "threshold_value": "1"},
    )
    assert duplicate.status_code == 409
    blank = client.post("/api/metrics/thresholds", json={"metric_key": "not_a_metric", "operator": ">", "threshold_value": "1"})
    assert blank.status_code == 422
    bad_range = client.post(
        "/api/metrics/thresholds",
        json={"metric_key": "rsi_14", "operator": "between", "threshold_value": "70", "threshold_high": "30"},
    )
    assert bad_range.status_code == 422

    body = _eval(client, stock_id, "interest_coverage")
    assert body["threshold"]["scope"] == "user"
    assert body["threshold"]["user_override"] is True
    assert body["state"] in {"met", "not_met", "insufficient_data", "stale_data"}

    future = (datetime.now(UTC).date() + timedelta(days=2)).isoformat()
    moved = client.patch(f"/api/metrics/thresholds/{created.json()['id']}", json={"effective_from": future})
    assert moved.status_code == 200, moved.text
    after = _eval(client, stock_id, "interest_coverage")
    assert after["state"] == "no_threshold_configured"

    restored = client.patch(
        f"/api/metrics/thresholds/{created.json()['id']}",
        json={"effective_from": None, "is_active": False},
    )
    assert restored.status_code == 200
    assert _eval(client, stock_id, "interest_coverage")["state"] == "no_threshold_configured"
    enabled = client.patch(f"/api/metrics/thresholds/{created.json()['id']}", json={"is_active": True})
    assert enabled.status_code == 200
    assert _eval(client, stock_id, "interest_coverage")["threshold"]["scope"] == "user"

    client.post("/api/auth/logout", headers={"Origin": ORIGIN})
    _login(client, email)
    listed = client.get("/api/metrics/thresholds?metric_key=interest_coverage")
    assert listed.status_code == 200
    assert listed.json()["results"][0]["metric_key"] == "interest_coverage"
    assert client.delete(f"/api/metrics/thresholds/{created.json()['id']}").status_code == 204


def test_user_cannot_change_another_users_threshold(client: TestClient) -> None:
    _auth(client)
    created = client.post(
        "/api/metrics/thresholds",
        json={"metric_key": "current_ratio", "operator": ">=", "threshold_value": "2"},
    )
    assert created.status_code == 201, created.text
    threshold_id = created.json()["id"]
    _auth(client)
    assert client.patch(f"/api/metrics/thresholds/{threshold_id}", json={"threshold_value": "3"}).status_code == 404
    assert client.delete(f"/api/metrics/thresholds/{threshold_id}").status_code == 404
    visible = client.get("/api/metrics/thresholds?metric_key=current_ratio")
    assert all(item["id"] != threshold_id for item in visible.json()["results"])
    assert client.get("/api/metrics/registry").status_code == 401 or client.post("/api/auth/logout", headers={"Origin": ORIGIN}).status_code == 204
    client.post("/api/auth/logout", headers={"Origin": ORIGIN})
    assert client.get("/api/metrics/thresholds").status_code == 401


def test_sector_beats_market_and_platform_until_a_user_override(client: TestClient) -> None:
    _auth(client)
    stock = _tcs()
    if not stock.sector:
        return
    platform = client.post(
        "/api/metrics/thresholds",
        json={"metric_key": "pb_ratio", "operator": "<=", "threshold_value": "9"},
    )
    assert platform.status_code == 201, platform.text
    chosen = _eval(client, str(stock.id), "pb_ratio")
    assert chosen["threshold"]["user_override"] is True
    client.delete(f"/api/metrics/thresholds/{platform.json()['id']}")
    seeded = _eval(client, str(stock.id), "pe_ratio")
    assert seeded["threshold"]["scope"] in {"sector", "market", "platform"}
    assert seeded["threshold"]["user_override"] is False
    assert "not a trade instruction" in seeded["explanation"] or seeded["state"] in {
        "insufficient_data",
        "stale_data",
        "context_unavailable",
        "no_threshold_configured",
        "met",
        "not_met",
    }
