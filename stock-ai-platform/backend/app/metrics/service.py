"""User threshold configuration and stock evaluation. Defaults are read-only here."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.metrics import DEFINITION_VERSION, REGISTRY_VERSION
from app.metrics.evaluate import Evaluation, evaluate_reading
from app.metrics.readings import load_context, reading_for
from app.metrics.registry import METRICS, MetricDefinition, get_metric, registry_payload
from app.metrics.resolve import as_of_date, resolve_threshold
from app.models import MetricThreshold, Stock, User
from app.models.enums import AlertOperator, MetricScope

NOT_FOUND = "not_found"
STOCK_NOT_FOUND = "stock_not_found"
UNKNOWN_METRIC = "unknown_metric"
INVALID_CONDITION = "invalid_condition"
DUPLICATE = "duplicate"
TOO_MANY = "too_many"
NOT_OWNER = "not_owner"

MESSAGES = {
    NOT_FOUND: "Threshold not found",
    STOCK_NOT_FOUND: "Stock not found",
    UNKNOWN_METRIC: "That metric is not supported",
    INVALID_CONDITION: "That threshold condition is not valid for this metric",
    DUPLICATE: "You already have an active threshold for this metric and stock",
    TOO_MANY: "You have reached the threshold limit",
    NOT_OWNER: "Threshold not found",
}


class ThresholdError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code


def list_registry() -> dict[str, object]:
    return registry_payload()


def list_thresholds(db: Session, user: User, *, metric_key: str | None, stock_id: UUID | None) -> list[MetricThreshold]:
    if metric_key is not None and get_metric(metric_key) is None:
        raise ThresholdError(UNKNOWN_METRIC)
    stock = _optional_stock(db, stock_id)
    statement = select(MetricThreshold).where(
        (MetricThreshold.user_id == user.id) | (MetricThreshold.scope != MetricScope.USER)
    )
    if metric_key is not None:
        statement = statement.where(MetricThreshold.metric_name == metric_key)
    rows = list(db.scalars(statement.order_by(MetricThreshold.metric_name, MetricThreshold.scope)).all())
    if stock is None:
        return rows
    return [
        row
        for row in rows
        if (row.scope == MetricScope.USER and row.user_id == user.id and (row.stock_id is None or row.stock_id == stock.id))
        or row.scope == MetricScope.GLOBAL
        or (row.scope == MetricScope.COUNTRY and row.country == stock.country)
        or (row.scope == MetricScope.SECTOR and row.sector == stock.sector and (row.country is None or row.country == stock.country))
    ]


def create_user_threshold(db: Session, user: User, payload: dict[str, object]) -> MetricThreshold:
    metric = _metric(str(payload["metric_key"]))
    stock = _optional_stock(db, payload.get("stock_id") if isinstance(payload.get("stock_id"), UUID) else None)
    _validate_condition(metric, payload)
    count = db.scalar(select(func.count()).select_from(MetricThreshold).where(MetricThreshold.user_id == user.id)) or 0
    if int(count) >= settings.threshold_max_user_overrides:
        raise ThresholdError(TOO_MANY)
    row = MetricThreshold(
        metric_name=metric.key,
        scope=MetricScope.USER,
        user_id=user.id,
        stock_id=stock.id if stock else None,
        operator=AlertOperator(str(payload["operator"])),
        basis=str(payload["basis"]),
        threshold_value=_decimal(payload.get("threshold_value")),
        threshold_high=_decimal(payload.get("threshold_high")),
        description=_text(payload.get("description")),
        definition_version=DEFINITION_VERSION,
        effective_from=payload.get("effective_from"),  # type: ignore[arg-type]
        effective_to=payload.get("effective_to"),  # type: ignore[arg-type]
        is_active=True,
    )
    db.add(row)
    _commit(db)
    db.refresh(row)
    return row


def update_user_threshold(db: Session, user: User, threshold_id: UUID, payload: dict[str, object]) -> MetricThreshold:
    row = _owned(db, user, threshold_id)
    metric = _metric(row.metric_name)
    merged = {
        "operator": payload.get("operator", row.operator.value if hasattr(row.operator, "value") else row.operator),
        "basis": payload.get("basis", row.basis),
        "threshold_value": payload["threshold_value"] if "threshold_value" in payload else row.threshold_value,
        "threshold_high": payload["threshold_high"] if "threshold_high" in payload else row.threshold_high,
        "description": payload["description"] if "description" in payload else row.description,
        "effective_from": payload["effective_from"] if "effective_from" in payload else row.effective_from,
        "effective_to": payload["effective_to"] if "effective_to" in payload else row.effective_to,
        "is_active": payload.get("is_active", row.is_active),
        "stock_id": payload["stock_id"] if "stock_id" in payload else row.stock_id,
    }
    if "stock_id" in payload:
        stock = _optional_stock(db, merged["stock_id"] if isinstance(merged["stock_id"], UUID) else None)
        row.stock_id = stock.id if stock else None
    _validate_condition(metric, merged)
    row.operator = AlertOperator(str(merged["operator"]))
    row.basis = str(merged["basis"])
    row.threshold_value = _decimal(merged["threshold_value"])
    row.threshold_high = _decimal(merged["threshold_high"])
    row.description = _text(merged["description"])
    row.effective_from = merged["effective_from"]  # type: ignore[assignment]
    row.effective_to = merged["effective_to"]  # type: ignore[assignment]
    row.is_active = bool(merged["is_active"])
    row.definition_version = DEFINITION_VERSION
    row.updated_at = datetime.now(UTC)
    _commit(db)
    db.refresh(row)
    return row


def delete_user_threshold(db: Session, user: User, threshold_id: UUID) -> None:
    row = _owned(db, user, threshold_id)
    db.delete(row)
    db.commit()


def evaluate_stock(db: Session, user: User, stock_id: UUID, metric_keys: list[str] | None, now: datetime | None = None) -> dict[str, object]:
    stock = _require_stock(db, stock_id)
    keys = metric_keys or [item.key for item in METRICS]
    if len(keys) > 40:
        raise ThresholdError(INVALID_CONDITION)
    metrics = [_metric(key) for key in keys]
    moment = now or datetime.now(UTC)
    context = load_context(db, stock, moment)
    rows = list(
        db.scalars(
            select(MetricThreshold).where(
                MetricThreshold.metric_name.in_([metric.key for metric in metrics]),
                (MetricThreshold.user_id == user.id) | (MetricThreshold.user_id.is_(None)),
            )
        ).all()
    )
    results = []
    for metric in metrics:
        candidates = [row for row in rows if row.metric_name == metric.key]
        _row, resolved, skipped = resolve_threshold(candidates, stock, as_of=as_of_date(moment))
        reading = reading_for(metric, context, moment)
        outcome = evaluate_reading(metric.name, reading, resolved, event_kind=metric.event_kind)
        results.append(_evaluation_body(metric, resolved, outcome, skipped, reading.as_of, reading.source))
    return {
        "stock_id": stock.id,
        "registry_version": REGISTRY_VERSION,
        "evaluated_at": moment,
        "results": results,
    }


def _evaluation_body(
    metric: MetricDefinition,
    resolved: object,
    outcome: Evaluation,
    skipped: list[str],
    as_of: datetime | None,
    source: str | None,
) -> dict[str, object]:
    threshold = None
    if resolved is not None:
        threshold = {
            "id": resolved.id,  # type: ignore[attr-defined]
            "scope": resolved.scope,  # type: ignore[attr-defined]
            "operator": resolved.operator,  # type: ignore[attr-defined]
            "basis": resolved.basis,  # type: ignore[attr-defined]
            "threshold_value": _text_decimal(resolved.threshold_value),  # type: ignore[attr-defined]
            "threshold_high": _text_decimal(resolved.threshold_high),  # type: ignore[attr-defined]
            "definition_version": resolved.definition_version,  # type: ignore[attr-defined]
            "effective_from": resolved.effective_from,  # type: ignore[attr-defined]
            "reason": resolved.reason,  # type: ignore[attr-defined]
            "skipped_scopes": skipped,
            "user_override": resolved.scope == "user",  # type: ignore[attr-defined]
        }
    return {
        "metric_key": metric.key,
        "metric_name": metric.name,
        "category": metric.category,
        "unit": metric.unit,
        "state": outcome.state,
        "explanation": outcome.explanation,
        "as_of": as_of,
        "source": source,
        "value": _text_decimal(outcome.value),
        "previous_value": _text_decimal(outcome.previous),
        "reference_value": _text_decimal(outcome.reference),
        "threshold": threshold,
    }


def _validate_condition(metric: MetricDefinition, payload: dict[str, object]) -> None:
    operator = str(payload["operator"])
    basis = str(payload["basis"])
    if operator not in metric.operators or basis not in {"absolute", "sector_benchmark"}:
        raise ThresholdError(INVALID_CONDITION)
    if basis == "sector_benchmark" and not metric.sector_benchmark:
        raise ThresholdError(INVALID_CONDITION)
    low = _decimal(payload.get("threshold_value"))
    high = _decimal(payload.get("threshold_high"))
    start = payload.get("effective_from")
    end = payload.get("effective_to")
    if start is not None and end is not None and end < start:  # type: ignore[operator]
        raise ThresholdError(INVALID_CONDITION)
    if basis == "sector_benchmark":
        if low is not None or high is not None or operator in {"between", "outside_range", "crosses_above", "crosses_below"}:
            raise ThresholdError(INVALID_CONDITION)
        return
    if metric.event_kind == "pair":
        if low is not None or high is not None:
            raise ThresholdError(INVALID_CONDITION)
        return
    if operator in {"between", "outside_range"}:
        if low is None or high is None or high <= low:
            raise ThresholdError(INVALID_CONDITION)
        return
    if low is None or high is not None:
        raise ThresholdError(INVALID_CONDITION)


def _metric(key: str) -> MetricDefinition:
    metric = get_metric(key)
    if metric is None:
        raise ThresholdError(UNKNOWN_METRIC)
    return metric


def _optional_stock(db: Session, stock_id: UUID | None) -> Stock | None:
    if stock_id is None:
        return None
    return _require_stock(db, stock_id)


def _require_stock(db: Session, stock_id: UUID) -> Stock:
    stock = db.get(Stock, stock_id)
    if stock is None or not stock.is_active or stock.country != "IN" or stock.currency != "INR" or stock.exchange not in {"NSE", "BSE"}:
        raise ThresholdError(STOCK_NOT_FOUND)
    return stock


def _owned(db: Session, user: User, threshold_id: UUID) -> MetricThreshold:
    row = db.get(MetricThreshold, threshold_id)
    if row is None or row.user_id != user.id or row.scope != MetricScope.USER:
        raise ThresholdError(NOT_FOUND)
    return row


def _text_decimal(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value, "f")


def _decimal(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _text(value: object) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(str(value).split())
    return cleaned or None


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ThresholdError(DUPLICATE) from None
