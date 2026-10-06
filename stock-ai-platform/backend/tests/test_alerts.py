import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.alerts.evaluator import evaluate_active, evaluate_alert
from app.core.database import engine, get_db
from app.main import app
from app.markets.time import IST
from app.models import Alert, AlertEvent, Notification, Stock, StockPrice, TechnicalPattern
from tests.isolation import hide_committed_market_rows

PASSWORD = "Validpass1"
ORIGIN = "http://localhost:5173"


def _auth(client: TestClient, name: str = "alerts") -> None:
    response = client.post(
        "/api/auth/register",
        json={"email": f"{name}-{uuid.uuid4().hex}@example.com", "password": PASSWORD, "full_name": "Alert Tester"},
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


def _bar(stock_id: uuid.UUID, moment: datetime, close: str) -> StockPrice:
    price = Decimal(close)
    return StockPrice(
        stock_id=stock_id,
        interval="1d",
        timestamp=moment,
        open=price,
        high=price,
        low=price,
        close=price,
        adjusted_close=price,
        volume=1000,
    )


def _price_alert(client: TestClient, stock_id: uuid.UUID, **overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "stock_id": str(stock_id),
        "category": "price",
        "metric": "price",
        "operator": ">",
        "threshold_type": "absolute",
        "threshold_value": "100",
        "repeat_mode": "once",
    }
    body.update(overrides)
    response = client.post("/api/alerts", json=body, headers={"Origin": ORIGIN})
    assert response.status_code == 201, response.text
    return response.json()


def test_rejects_unknown_metric_and_lists_catalog(client: TestClient) -> None:
    _auth(client)
    db = _db()
    stock = _tcs(db)
    rejected = client.post(
        "/api/alerts",
        json={
            "stock_id": str(stock.id),
            "category": "fundamental",
            "metric": "not_a_metric",
            "operator": ">",
            "threshold_type": "absolute",
            "threshold_value": "1",
        },
        headers={"Origin": ORIGIN},
    )
    assert rejected.status_code == 422
    catalog = client.get("/api/alerts/catalog")
    assert catalog.status_code == 200
    assert "email_delivery" not in catalog.json()
    assert "price" in catalog.json()["price"]["metrics"][0]["key"]


def test_price_alert_triggers_once_and_preview_does_not_forge_an_event(client: TestClient) -> None:
    _auth(client)
    db = _db()
    stock = _tcs(db)
    now = datetime.now(IST)
    db.add(_bar(stock.id, now - timedelta(days=1), "90"))
    db.add(_bar(stock.id, now, "110"))
    db.commit()
    created = _price_alert(client, stock.id, threshold_value="100", repeat_mode="once")
    preview = client.post(f"/api/alerts/{created['id']}/preview")
    assert preview.status_code == 200
    assert preview.json()["preview"] is True
    assert preview.json()["state"] == "met"
    assert db.scalar(select(func.count()).select_from(AlertEvent)) == 0
    alert = db.get(Alert, uuid.UUID(created["id"]))
    assert alert is not None
    assert evaluate_alert(db, alert, datetime.now(UTC)) == "triggered"
    db.commit()
    assert evaluate_alert(db, alert, datetime.now(UTC)) == "inactive"
    assert db.scalar(select(func.count()).select_from(AlertEvent).where(AlertEvent.alert_id == alert.id)) == 1


def test_repeat_holds_while_true_then_rearms(client: TestClient) -> None:
    _auth(client)
    db = _db()
    stock = _tcs(db)
    now = datetime.now(IST)
    first = _bar(stock.id, now - timedelta(days=1), "90")
    second = _bar(stock.id, now, "110")
    db.add(first)
    db.add(second)
    db.commit()
    created = _price_alert(client, stock.id, threshold_value="100", repeat_mode="repeat")
    alert = db.get(Alert, uuid.UUID(created["id"]))
    assert alert is not None
    assert evaluate_alert(db, alert, datetime.now(UTC)) == "triggered"
    assert evaluate_alert(db, alert, datetime.now(UTC)) == "held"
    second.close = Decimal("80")
    db.commit()
    assert evaluate_alert(db, alert, datetime.now(UTC)) == "not_met"
    assert alert.armed is True
    second.close = Decimal("130")
    db.commit()
    assert evaluate_alert(db, alert, datetime.now(UTC)) == "triggered"
    assert db.scalar(select(func.count()).select_from(AlertEvent).where(AlertEvent.alert_id == alert.id)) == 2


def test_cross_and_stale_and_missing_do_not_invent_a_trigger(client: TestClient) -> None:
    _auth(client)
    db = _db()
    stock = _tcs(db)
    created = _price_alert(client, stock.id, operator="crosses_above", threshold_value="100")
    alert = db.get(Alert, uuid.UUID(created["id"]))
    assert alert is not None
    assert evaluate_alert(db, alert, datetime.now(UTC)) == "insufficient_data"
    now = datetime.now(IST)
    db.add(_bar(stock.id, now, "110"))
    db.commit()
    assert evaluate_alert(db, alert, datetime.now(UTC)) == "insufficient_data"
    db.add(_bar(stock.id, now - timedelta(days=1), "90"))
    db.commit()
    assert evaluate_alert(db, alert, datetime.now(UTC)) == "triggered"
    stale = _price_alert(client, stock.id, threshold_value="1", repeat_mode="repeat")
    stale_alert = db.get(Alert, uuid.UUID(stale["id"]))
    assert stale_alert is not None
    for row in db.scalars(select(StockPrice).where(StockPrice.stock_id == stock.id)).all():
        row.timestamp = datetime.now(IST) - timedelta(days=30)
    db.commit()
    assert evaluate_alert(db, stale_alert, datetime.now(UTC)) == "stale_data"
    assert db.scalar(select(func.count()).select_from(AlertEvent).where(AlertEvent.alert_id == stale_alert.id)) == 0


def test_duplicate_key_and_notification_read_keep_the_event(client: TestClient) -> None:
    _auth(client)
    db = _db()
    stock = _tcs(db)
    now = datetime.now(IST)
    db.add(_bar(stock.id, now, "150"))
    db.commit()
    created = _price_alert(client, stock.id, threshold_value="100", repeat_mode="repeat")
    alert = db.get(Alert, uuid.UUID(created["id"]))
    assert alert is not None
    assert evaluate_alert(db, alert, datetime.now(UTC)) == "triggered"
    alert.armed = True
    db.commit()
    assert evaluate_alert(db, alert, datetime.now(UTC)) == "duplicate"
    assert db.scalar(select(func.count()).select_from(AlertEvent).where(AlertEvent.alert_id == alert.id)) == 1
    inbox = client.get("/api/notifications")
    assert inbox.status_code == 200
    body = inbox.json()
    assert body["unread"] == 1
    note_id = body["results"][0]["id"]
    marked = client.post(f"/api/notifications/{note_id}/read")
    assert marked.status_code == 200
    assert marked.json()["read_at"] is not None
    assert db.scalar(select(func.count()).select_from(AlertEvent).where(AlertEvent.alert_id == alert.id)) == 1
    history = client.get(f"/api/alerts/{alert.id}/events")
    assert history.status_code == 200
    assert history.json()["total"] == 1


def test_ownership_pause_and_in_app_preference(client: TestClient) -> None:
    _auth(client, "owner")
    db = _db()
    stock = _tcs(db)
    created = _price_alert(client, stock.id)
    other = TestClient(app)
    _auth(other, "other")
    assert other.get(f"/api/alerts/{created['id']}").status_code == 404
    assert other.patch(f"/api/alerts/{created['id']}", json={"note": "nope"}).status_code == 404
    paused = client.post(f"/api/alerts/{created['id']}/pause")
    assert paused.status_code == 200
    assert paused.json()["status"] == "paused"
    listed = client.get("/api/alerts?limit=1&offset=0")
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    saved = client.patch("/api/notifications/preferences", json={"in_app_enabled": False})
    assert saved.status_code == 200
    assert saved.json() == {"in_app_enabled": False}
    assert client.delete(f"/api/alerts/{created['id']}").status_code == 204


def test_pattern_confirmation_uses_stored_detector_status(client: TestClient) -> None:
    _auth(client)
    db = _db()
    stock = _tcs(db)
    moment = datetime.now(UTC)
    db.add(
        TechnicalPattern(
            stock_id=stock.id,
            pattern_type="double_top",
            direction="bearish",
            status="confirmed",
            interval="1d",
            start_timestamp=moment - timedelta(days=20),
            end_timestamp=moment,
            key_levels={"neckline": "1"},
            pivot_evidence=[],
            evidence_summary="Test fixture, not a live pattern.",
            detector_version="patterns-1",
            source_price_as_of=moment,
            calculated_at=moment,
        )
    )
    db.commit()
    created = client.post(
        "/api/alerts",
        json={
            "stock_id": str(stock.id),
            "category": "pattern",
            "metric": "pattern",
            "operator": ">",
            "threshold_type": "absolute",
            "pattern_type": "double_top",
            "pattern_status": "confirmed",
            "repeat_mode": "once",
        },
        headers={"Origin": ORIGIN},
    )
    assert created.status_code == 201, created.text
    alert = db.get(Alert, uuid.UUID(created.json()["id"]))
    assert alert is not None
    assert evaluate_alert(db, alert, moment) == "triggered"
    note = db.scalar(select(Notification).where(Notification.user_id == alert.user_id))
    assert note is not None
    assert "double top" in db.scalar(select(AlertEvent.message).where(AlertEvent.alert_id == alert.id))


def test_fundamental_without_a_stored_reading_does_not_trigger(client: TestClient) -> None:
    _auth(client)
    db = _db()
    stock = _tcs(db)
    created = client.post(
        "/api/alerts",
        json={
            "stock_id": str(stock.id),
            "category": "fundamental",
            "metric": "pe_ratio",
            "operator": "<=",
            "threshold_type": "sector_relative",
            "repeat_mode": "repeat",
        },
        headers={"Origin": ORIGIN},
    )
    assert created.status_code == 201, created.text
    alert = db.get(Alert, uuid.UUID(created.json()["id"]))
    assert alert is not None
    action = evaluate_alert(db, alert, datetime.now(UTC))
    assert action in {"insufficient_data", "no_threshold_configured", "context_unavailable", "stale_data"}
    assert db.scalar(select(func.count()).select_from(AlertEvent).where(AlertEvent.alert_id == alert.id)) == 0


def test_second_worker_skips_while_the_advisory_lock_is_held(client: TestClient) -> None:
    _auth(client)
    other = engine.connect()
    try:
        assert other.execute(text("SELECT pg_try_advisory_lock(81411011)")).scalar() is True
        assert evaluate_active(_db()) == {"skipped": 1}
    finally:
        other.execute(text("SELECT pg_advisory_unlock(81411011)"))
        other.close()
