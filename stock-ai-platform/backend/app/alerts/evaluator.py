"""Evaluate stored alerts. This module does not call market-data providers or an LLM.

Price checks use stored daily closes and the threshold engine's comparison
functions. Fundamental and technical checks use the metric registry readings
and `evaluate_reading`. Pattern checks use stored detector rows.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.alerts.catalog import PATTERN_STATUSES, PATTERN_TYPES
from app.markets.time import IST
from app.metrics.evaluate import ResolvedThreshold, cross_met, evaluate_reading, level_met
from app.metrics.readings import load_context, reading_for
from app.metrics.registry import get_metric
from app.metrics.resolve import as_of_date, resolve_threshold
from app.models import Alert, AlertEvent, MetricThreshold, Notification, NotificationPreference, Stock, StockPrice, TechnicalPattern, User
from app.models.enums import MetricScope
from app.services.fundamental_math import growth_percent
from app.services.technical_service import STALE_DAYS

TRIGGER_STATES = frozenset({"met"})
QUIET_STATES = frozenset(
    {"not_met", "insufficient_data", "stale_data", "context_unavailable", "no_threshold_configured"}
)


@dataclass(frozen=True)
class Observation:
    state: str
    explanation: str
    value: Decimal | None
    previous: Decimal | None
    reference: Decimal | None
    as_of: datetime | None
    source: str | None
    pattern_id: UUID | None = None
    pattern_status: str | None = None


def observe(db: Session, alert: Alert, stock: Stock, user: User, now: datetime) -> Observation:
    if alert.category == "price":
        return _price(db, alert, stock, now)
    if alert.category == "pattern":
        return _pattern(db, alert, stock)
    return _metric(db, alert, stock, user, now)


def apply_observation(db: Session, alert: Alert, observation: Observation, now: datetime) -> str:
    """Update lifecycle and, when armed and met, persist one event. Returns the action taken."""
    alert.last_evaluated_at = now
    alert.last_data_status = observation.state
    if observation.value is not None:
        alert.previous_value = observation.previous
        alert.last_value = observation.value
    if alert.status != "active":
        db.flush()
        return "inactive"
    if observation.state in {"insufficient_data", "stale_data", "context_unavailable", "no_threshold_configured"}:
        db.flush()
        return observation.state
    if observation.state != "met":
        _rearm_if_clear(alert, observation)
        db.flush()
        return "not_met"
    if not alert.armed:
        db.flush()
        return "held"
    if alert.category == "pattern" and observation.pattern_id is not None and alert.last_pattern_id == observation.pattern_id and alert.last_pattern_status == observation.pattern_status:
        db.flush()
        return "held"
    created = _record_event(db, alert, observation, now)
    if not created:
        db.flush()
        return "duplicate"
    alert.armed = False
    if observation.pattern_id is not None:
        alert.last_pattern_id = observation.pattern_id
        alert.last_pattern_status = observation.pattern_status
    if alert.repeat_mode == "once":
        alert.status = "triggered"
        alert.is_active = False
    db.flush()
    return "triggered"


def evaluate_alert(db: Session, alert: Alert, now: datetime | None = None) -> str:
    moment = now or datetime.now(UTC)
    stock = db.get(Stock, alert.stock_id)
    user = db.get(User, alert.user_id)
    if stock is None or user is None:
        alert.last_evaluated_at = moment
        alert.last_data_status = "insufficient_data"
        db.flush()
        return "insufficient_data"
    observation = observe(db, alert, stock, user, moment)
    return apply_observation(db, alert, observation, moment)


def evaluate_active(db: Session, now: datetime | None = None) -> dict[str, int]:
    """Evaluate every active alert. One database advisory lock keeps workers from overlapping."""
    moment = now or datetime.now(UTC)
    locked = db.execute(select_lock()).scalar()
    if not locked:
        return {"skipped": 1}
    counts = {"evaluated": 0, "triggered": 0, "held": 0, "not_met": 0, "insufficient_data": 0, "stale_data": 0}
    try:
        alerts = list(db.scalars(select(Alert).where(Alert.status == "active")).all())
        for alert in alerts:
            action = evaluate_alert(db, alert, moment)
            counts["evaluated"] += 1
            counts[action] = counts.get(action, 0) + 1
        db.commit()
    finally:
        db.execute(unlock())
        db.commit()
    return counts


def select_lock():
    from sqlalchemy import text

    return text("SELECT pg_try_advisory_lock(81411011)")


def unlock():
    from sqlalchemy import text

    return text("SELECT pg_advisory_unlock(81411011)")


def _rearm_if_clear(alert: Alert, observation: Observation) -> None:
    if alert.category == "pattern":
        if observation.pattern_status and observation.pattern_status != alert.pattern_status:
            if not alert.armed:
                alert.armed = True
                alert.arm_generation += 1
            alert.last_pattern_status = observation.pattern_status
        return
    if not alert.armed:
        alert.armed = True
        alert.arm_generation += 1


def _record_event(db: Session, alert: Alert, observation: Observation, now: datetime) -> bool:
    stamp = observation.as_of.isoformat() if observation.as_of is not None else "none"
    pattern = str(observation.pattern_id) if observation.pattern_id is not None else ""
    key = f"{alert.id}:{alert.arm_generation}:{stamp}:{pattern}"
    value = observation.value if observation.value is not None else Decimal("0")
    threshold = alert.threshold_value if alert.threshold_value is not None else (observation.reference or Decimal("0"))
    event = AlertEvent(
        alert_id=alert.id,
        user_id=alert.user_id,
        stock_id=alert.stock_id,
        triggered_value=value,
        previous_value=observation.previous,
        threshold_value=threshold,
        triggered_at=now,
        observed_at=observation.as_of,
        message=observation.explanation,
        data_status="fresh",
        source=observation.source,
        idempotency_key=key,
        is_read=False,
    )
    nested = db.begin_nested()
    try:
        db.add(event)
        db.flush()
        preference = db.get(NotificationPreference, alert.user_id)
        if preference is None or preference.in_app_enabled:
            db.add(Notification(user_id=alert.user_id, alert_event_id=event.id))
            db.flush()
        nested.commit()
    except IntegrityError:
        nested.rollback()
        return False
    return True


def _metric(db: Session, alert: Alert, stock: Stock, user: User, now: datetime) -> Observation:
    metric = get_metric(alert.metric)
    if metric is None:
        return Observation("insufficient_data", "That metric is not supported.", None, None, None, None, None)
    context = load_context(db, stock, now)
    reading = reading_for(metric, context, now)
    kind = alert.threshold_type.value if hasattr(alert.threshold_type, "value") else str(alert.threshold_type)
    if kind == "sector_relative":
        resolved, skipped = _resolved_sector(db, alert, stock, user, now)
        outcome = evaluate_reading(metric.name, reading, resolved, event_kind=metric.event_kind)
        if skipped and outcome.state == "met":
            outcome_explanation = f"{outcome.explanation} Skipped scopes: {', '.join(skipped)}."
        else:
            outcome_explanation = outcome.explanation
        return Observation(outcome.state, outcome_explanation, outcome.value, outcome.previous, outcome.reference, reading.as_of, reading.source)
    operator = alert.operator.value if hasattr(alert.operator, "value") else str(alert.operator)
    resolved = ResolvedThreshold(
        id=str(alert.id),
        metric_key=metric.key,
        scope="user",
        operator=operator,
        basis="absolute",
        threshold_value=alert.threshold_value,
        threshold_high=alert.threshold_high,
        definition_version="alert",
        effective_from=None,
        description=alert.note,
        reason="Using the threshold stored on this alert.",
        skipped=[],
    )
    outcome = evaluate_reading(metric.name, reading, resolved, event_kind=metric.event_kind)
    return Observation(outcome.state, outcome.explanation, outcome.value, outcome.previous, outcome.reference, reading.as_of, reading.source)


def _resolved_sector(db: Session, alert: Alert, stock: Stock, user: User, now: datetime):
    rows = list(
        db.scalars(
            select(MetricThreshold).where(
                MetricThreshold.metric_name == alert.metric,
                (MetricThreshold.user_id == user.id) | (MetricThreshold.user_id.is_(None)),
            )
        ).all()
    )
    _row, resolved, skipped = resolve_threshold(rows, stock, as_of=as_of_date(now))
    return resolved, skipped


def _price(db: Session, alert: Alert, stock: Stock, now: datetime) -> Observation:
    bars = list(
        db.scalars(
            select(StockPrice)
            .where(StockPrice.stock_id == stock.id, StockPrice.interval == "1d")
            .order_by(StockPrice.timestamp.desc())
            .limit(25)
        ).all()
    )
    if not bars:
        return Observation("insufficient_data", "No stored daily close is available for this stock.", None, None, None, None, "stock_prices")
    latest = bars[0]
    if _price_stale(latest.timestamp, now):
        return Observation(
            "stale_data",
            "The latest stored daily close is older than the freshness window, so it was not compared.",
            latest.close,
            bars[1].close if len(bars) > 1 else None,
            None,
            latest.timestamp,
            "stock_prices",
        )
    operator = alert.operator.value if hasattr(alert.operator, "value") else str(alert.operator)
    if alert.metric == "price_change_percent":
        return _percent_move(alert, bars, operator, latest)
    previous = bars[1].close if len(bars) > 1 else None
    if operator in {"crosses_above", "crosses_below"}:
        met = cross_met(operator, previous, latest.close, alert.threshold_value)
        if met is None:
            return Observation(
                "insufficient_data",
                "A price cross needs the previous stored close and the current close. One close is not a cross.",
                latest.close,
                previous,
                None,
                latest.timestamp,
                "stock_prices",
            )
    else:
        met = level_met(operator, latest.close, alert.threshold_value, alert.threshold_high)
        if met is None:
            return Observation("insufficient_data", "The price condition is incomplete.", latest.close, previous, None, latest.timestamp, "stock_prices")
    relation = "meets" if met else "does not meet"
    return Observation(
        "met" if met else "not_met",
        f"The stored close is {latest.close} and {relation} the alert ({operator} {alert.threshold_value}). This is not a trade instruction.",
        latest.close,
        previous,
        None,
        latest.timestamp,
        "stock_prices",
    )


def _percent_move(alert: Alert, bars: list[StockPrice], operator: str, latest: StockPrice) -> Observation:
    steps = {"1d": 1, "5d": 5, "20d": 20}.get(alert.percent_interval or "", 0)
    if steps <= 0 or len(bars) <= steps or alert.threshold_value is None:
        return Observation(
            "insufficient_data",
            "That percent move needs enough stored daily closes for the selected interval.",
            latest.close,
            None,
            None,
            latest.timestamp,
            "stock_prices",
        )
    earlier = bars[steps]
    change = growth_percent(latest.close, earlier.close)
    if change is None:
        return Observation("insufficient_data", "The percent move is undefined for these closes.", latest.close, earlier.close, None, latest.timestamp, "stock_prices")
    magnitude = abs(alert.threshold_value)
    bound = magnitude if operator == ">" else -magnitude
    compare = ">" if operator == ">" else "<"
    met = level_met(compare, change, bound, None)
    relation = "meets" if met else "does not meet"
    return Observation(
        "met" if met else "not_met",
        f"The stored close moved {change} percent points versus the close {steps} sessions earlier and {relation} the alert. This is not a trade instruction.",
        change,
        earlier.close,
        None,
        latest.timestamp,
        "stock_prices",
    )


def _pattern(db: Session, alert: Alert, stock: Stock) -> Observation:
    if alert.pattern_type not in PATTERN_TYPES or alert.pattern_status not in PATTERN_STATUSES:
        return Observation("insufficient_data", "That pattern alert is not supported.", None, None, None, None, "technical_patterns")
    pattern = db.scalar(
        select(TechnicalPattern)
        .where(
            TechnicalPattern.stock_id == stock.id,
            TechnicalPattern.interval == "1d",
            TechnicalPattern.pattern_type == alert.pattern_type,
        )
        .order_by(TechnicalPattern.source_price_as_of.desc())
        .limit(1)
    )
    if pattern is None:
        return Observation("insufficient_data", "No stored daily pattern of that type is available.", None, None, None, None, "technical_patterns")
    met = pattern.status == alert.pattern_status
    explanation = (
        f"The stored {pattern.pattern_type.replace('_', ' ')} pattern is {pattern.status} as of {pattern.source_price_as_of.isoformat()}. "
        "This is not a trade instruction."
    )
    return Observation(
        "met" if met else "not_met",
        explanation,
        None,
        None,
        None,
        pattern.source_price_as_of,
        "technical_patterns",
        pattern.id,
        pattern.status,
    )


def _price_stale(stamp: datetime, now: datetime) -> bool:
    return stamp.astimezone(IST).date() < now.astimezone(IST).date() - timedelta(days=STALE_DAYS)
