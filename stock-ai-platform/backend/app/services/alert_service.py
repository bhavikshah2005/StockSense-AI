"""User-owned alerts and in-app notifications. Evaluation lives in app.alerts.evaluator."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.alerts.catalog import PATTERN_STATUSES, PATTERN_TYPES, PERCENT_OPERATORS, PRICE_INTERVALS, PRICE_OPERATORS
from app.alerts.evaluator import evaluate_alert, observe
from app.core.config import settings
from app.metrics.registry import get_metric
from app.models import Alert, AlertEvent, Notification, NotificationPreference, Stock, User
from app.models.enums import AlertOperator, ThresholdType

NOT_FOUND = "not_found"
STOCK_NOT_FOUND = "stock_not_found"
INVALID = "invalid"
TOO_MANY = "too_many"

MESSAGES = {
    NOT_FOUND: "Alert not found",
    STOCK_NOT_FOUND: "Stock not found",
    INVALID: "That alert condition is not supported",
    TOO_MANY: "You have reached the alert limit",
}


class AlertError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code


def list_alerts(db: Session, user: User, *, limit: int, offset: int) -> tuple[list[Alert], int]:
    base = select(Alert).where(Alert.user_id == user.id)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = list(db.scalars(base.order_by(Alert.updated_at.desc()).limit(limit).offset(offset)).all())
    return rows, int(total)


def create_alert(db: Session, user: User, payload: dict[str, object]) -> Alert:
    stock = _stock(db, payload.get("stock_id"))
    _validate(payload)
    count = db.scalar(select(func.count()).select_from(Alert).where(Alert.user_id == user.id)) or 0
    if int(count) >= settings.alert_max_per_user:
        raise AlertError(TOO_MANY)
    row = Alert(
        user_id=user.id,
        stock_id=stock.id,
        category=str(payload["category"]),
        metric=str(payload["metric"]),
        operator=AlertOperator(str(payload["operator"])),
        threshold_type=ThresholdType(str(payload["threshold_type"])),
        threshold_value=_decimal(payload.get("threshold_value")),
        threshold_high=_decimal(payload.get("threshold_high")),
        sector_adjusted=str(payload["threshold_type"]) == "sector_relative",
        pattern_type=_text(payload.get("pattern_type")),
        pattern_status=_text(payload.get("pattern_status")),
        percent_interval=_text(payload.get("percent_interval")),
        repeat_mode=str(payload.get("repeat_mode") or "once"),
        status="active",
        is_active=True,
        armed=True,
        note=_text(payload.get("note")),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_alert(db: Session, user: User, alert_id: UUID) -> Alert:
    return _owned(db, user, alert_id)


def update_alert(db: Session, user: User, alert_id: UUID, payload: dict[str, object]) -> Alert:
    row = _owned(db, user, alert_id)
    merged = _merged(row, payload)
    if "stock_id" in payload:
        merged["stock_id"] = payload["stock_id"]
    _validate(merged)
    condition_changed = _condition_changed(row, merged)
    if "stock_id" in payload:
        row.stock_id = _stock(db, payload.get("stock_id")).id
    row.category = str(merged["category"])
    row.metric = str(merged["metric"])
    row.operator = AlertOperator(str(merged["operator"]))
    row.threshold_type = ThresholdType(str(merged["threshold_type"]))
    row.threshold_value = _decimal(merged.get("threshold_value"))
    row.threshold_high = _decimal(merged.get("threshold_high"))
    row.sector_adjusted = str(merged["threshold_type"]) == "sector_relative"
    row.pattern_type = _text(merged.get("pattern_type"))
    row.pattern_status = _text(merged.get("pattern_status"))
    row.percent_interval = _text(merged.get("percent_interval"))
    row.repeat_mode = str(merged["repeat_mode"])
    row.note = _text(merged.get("note"))
    if condition_changed and row.status == "active":
        row.armed = True
        row.arm_generation += 1
    db.commit()
    db.refresh(row)
    return row


def delete_alert(db: Session, user: User, alert_id: UUID) -> None:
    row = _owned(db, user, alert_id)
    db.delete(row)
    db.commit()


def pause_alert(db: Session, user: User, alert_id: UUID) -> Alert:
    row = _owned(db, user, alert_id)
    if row.status != "active":
        raise AlertError(INVALID)
    row.status = "paused"
    row.is_active = False
    db.commit()
    db.refresh(row)
    return row


def resume_alert(db: Session, user: User, alert_id: UUID) -> Alert:
    row = _owned(db, user, alert_id)
    if row.status not in {"paused", "triggered"}:
        raise AlertError(INVALID)
    row.status = "active"
    row.is_active = True
    row.armed = True
    row.arm_generation += 1
    db.commit()
    db.refresh(row)
    return row


def list_events(db: Session, user: User, alert_id: UUID, *, limit: int, offset: int) -> tuple[list[AlertEvent], int]:
    alert = _owned(db, user, alert_id)
    base = select(AlertEvent).where(AlertEvent.alert_id == alert.id, AlertEvent.user_id == user.id)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = list(db.scalars(base.order_by(AlertEvent.triggered_at.desc()).limit(limit).offset(offset)).all())
    return rows, int(total)


def preview_alert(db: Session, user: User, alert_id: UUID) -> dict[str, object]:
    row = _owned(db, user, alert_id)
    stock = db.get(Stock, row.stock_id)
    if stock is None:
        raise AlertError(STOCK_NOT_FOUND)
    observation = observe(db, row, stock, user, datetime.now(UTC))
    return {
        "alert_id": row.id,
        "preview": True,
        "state": observation.state,
        "explanation": observation.explanation,
        "value": _text_decimal(observation.value),
        "previous_value": _text_decimal(observation.previous),
        "reference_value": _text_decimal(observation.reference),
        "observed_at": observation.as_of,
        "source": observation.source,
        "would_trigger": observation.state == "met" and row.armed and row.status == "active",
    }


def run_user_evaluation(db: Session, user: User, alert_id: UUID) -> str:
    """Evaluate one owned alert now. Used by tests and the worker, not as a forged trigger."""
    row = _owned(db, user, alert_id)
    action = evaluate_alert(db, row, datetime.now(UTC))
    db.commit()
    return action


def list_notifications(db: Session, user: User, *, unread: bool | None, limit: int, offset: int) -> tuple[list[Notification], int]:
    statement = select(Notification).where(Notification.user_id == user.id)
    if unread is True:
        statement = statement.where(Notification.read_at.is_(None))
    if unread is False:
        statement = statement.where(Notification.read_at.is_not(None))
    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    rows = list(db.scalars(statement.order_by(Notification.created_at.desc()).limit(limit).offset(offset)).all())
    return rows, int(total)


def unread_count(db: Session, user: User) -> int:
    total = db.scalar(
        select(func.count()).select_from(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None))
    )
    return int(total or 0)


def mark_read(db: Session, user: User, notification_id: UUID) -> Notification:
    row = db.scalar(select(Notification).where(Notification.id == notification_id, Notification.user_id == user.id))
    if row is None:
        raise AlertError(NOT_FOUND)
    if row.read_at is None:
        row.read_at = datetime.now(UTC)
        db.commit()
        db.refresh(row)
    return row


def mark_all_read(db: Session, user: User) -> int:
    rows = list(db.scalars(select(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None))).all())
    moment = datetime.now(UTC)
    for row in rows:
        row.read_at = moment
    db.commit()
    return len(rows)


def get_preferences(db: Session, user: User) -> NotificationPreference:
    row = db.get(NotificationPreference, user.id)
    if row is None:
        row = NotificationPreference(user_id=user.id, in_app_enabled=True)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def update_preferences(db: Session, user: User, payload: dict[str, object]) -> NotificationPreference:
    row = get_preferences(db, user)
    if "in_app_enabled" in payload:
        row.in_app_enabled = bool(payload["in_app_enabled"])
    db.commit()
    db.refresh(row)
    return row


def _validate(payload: dict[str, object]) -> None:
    category = str(payload.get("category") or "")
    metric = str(payload.get("metric") or "")
    operator = str(payload.get("operator") or "")
    threshold_type = str(payload.get("threshold_type") or "")
    repeat_mode = str(payload.get("repeat_mode") or "once")
    if repeat_mode not in {"once", "repeat"} or category not in {"price", "fundamental", "technical", "pattern"}:
        raise AlertError(INVALID)
    note = payload.get("note")
    if isinstance(note, str) and len(note) > 280:
        raise AlertError(INVALID)
    if category == "price":
        _validate_price(metric, operator, threshold_type, payload)
        return
    if category == "pattern":
        if payload.get("pattern_type") not in PATTERN_TYPES or payload.get("pattern_status") not in PATTERN_STATUSES:
            raise AlertError(INVALID)
        if metric != "pattern" or operator != ">" or threshold_type != "absolute":
            raise AlertError(INVALID)
        return
    definition = get_metric(metric)
    if definition is None or definition.category != category or operator not in definition.operators:
        raise AlertError(INVALID)
    if threshold_type == "sector_relative":
        if not definition.sector_benchmark or operator in {"crosses_above", "crosses_below", "between", "outside_range"}:
            raise AlertError(INVALID)
        return
    if threshold_type != "absolute":
        raise AlertError(INVALID)
    _require_bounds(operator, payload)


def _validate_price(metric: str, operator: str, threshold_type: str, payload: dict[str, object]) -> None:
    if metric == "price":
        if operator not in PRICE_OPERATORS or threshold_type != "absolute":
            raise AlertError(INVALID)
        _require_bounds(operator, payload)
        return
    if metric == "price_change_percent":
        if operator not in PERCENT_OPERATORS or threshold_type != "percentage":
            raise AlertError(INVALID)
        if payload.get("percent_interval") not in PRICE_INTERVALS:
            raise AlertError(INVALID)
        value = _decimal(payload.get("threshold_value"))
        if value is None or value <= 0:
            raise AlertError(INVALID)
        return
    raise AlertError(INVALID)


def _require_bounds(operator: str, payload: dict[str, object]) -> None:
    low = _decimal(payload.get("threshold_value"))
    high = _decimal(payload.get("threshold_high"))
    if operator in {"between", "outside_range"}:
        if low is None or high is None or high <= low:
            raise AlertError(INVALID)
        return
    if low is None or high is not None:
        raise AlertError(INVALID)


def _merged(row: Alert, payload: dict[str, object]) -> dict[str, object]:
    operator = row.operator.value if hasattr(row.operator, "value") else str(row.operator)
    threshold_type = row.threshold_type.value if hasattr(row.threshold_type, "value") else str(row.threshold_type)
    return {
        "category": payload.get("category", row.category),
        "metric": payload.get("metric", row.metric),
        "operator": payload.get("operator", operator),
        "threshold_type": payload.get("threshold_type", threshold_type),
        "threshold_value": payload["threshold_value"] if "threshold_value" in payload else row.threshold_value,
        "threshold_high": payload["threshold_high"] if "threshold_high" in payload else row.threshold_high,
        "pattern_type": payload["pattern_type"] if "pattern_type" in payload else row.pattern_type,
        "pattern_status": payload["pattern_status"] if "pattern_status" in payload else row.pattern_status,
        "percent_interval": payload["percent_interval"] if "percent_interval" in payload else row.percent_interval,
        "repeat_mode": payload.get("repeat_mode", row.repeat_mode),
        "note": payload["note"] if "note" in payload else row.note,
        "stock_id": row.stock_id,
    }


def _condition_changed(row: Alert, merged: dict[str, object]) -> bool:
    operator = row.operator.value if hasattr(row.operator, "value") else str(row.operator)
    threshold_type = row.threshold_type.value if hasattr(row.threshold_type, "value") else str(row.threshold_type)
    current = (row.metric, operator, threshold_type, row.threshold_value, row.threshold_high, row.pattern_type, row.pattern_status, row.percent_interval, row.stock_id)
    updated = (
        merged["metric"],
        str(merged["operator"]),
        str(merged["threshold_type"]),
        _decimal(merged.get("threshold_value")),
        _decimal(merged.get("threshold_high")),
        merged.get("pattern_type"),
        merged.get("pattern_status"),
        merged.get("percent_interval"),
        merged.get("stock_id"),
    )
    return current != updated


def _owned(db: Session, user: User, alert_id: UUID) -> Alert:
    row = db.get(Alert, alert_id)
    if row is None or row.user_id != user.id:
        raise AlertError(NOT_FOUND)
    return row


def _stock(db: Session, stock_id: object) -> Stock:
    if not isinstance(stock_id, UUID):
        raise AlertError(STOCK_NOT_FOUND)
    stock = db.get(Stock, stock_id)
    if stock is None:
        raise AlertError(STOCK_NOT_FOUND)
    return stock


def _decimal(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _text_decimal(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value, "f")
