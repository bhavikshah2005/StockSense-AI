"""Read stored metric values. This module does not call a market-data provider."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis.config import INDICATOR_VERSION
from app.analysis.indicators import percent_distance
from app.core.config import settings
from app.markets.time import IST
from app.metrics.registry import MetricDefinition
from app.metrics.evaluate import MetricReading
from app.models import Fundamental, SectorBenchmark, Stock, StockPrice, TechnicalIndicator, ValuationSnapshot
from app.services.fundamental_math import annual_cagr, cfo_to_net_profit
from app.services.technical_service import STALE_DAYS


@dataclass
class StoredContext:
    fundamentals: list[Fundamental]
    valuation: ValuationSnapshot | None
    indicators: list[TechnicalIndicator]
    close: Decimal | None
    close_at: datetime | None
    volume: int | None
    benchmark: SectorBenchmark | None


def load_context(db: Session, stock: Stock, now: datetime) -> StoredContext:
    fundamentals = list(
        db.scalars(select(Fundamental).where(Fundamental.stock_id == stock.id).order_by(Fundamental.report_date.desc())).all()
    )
    valuation = db.scalar(
        select(ValuationSnapshot).where(ValuationSnapshot.stock_id == stock.id).order_by(ValuationSnapshot.snapshot_at.desc()).limit(1)
    )
    indicators = list(
        db.scalars(
            select(TechnicalIndicator)
            .where(
                TechnicalIndicator.stock_id == stock.id,
                TechnicalIndicator.interval == "1d",
                TechnicalIndicator.calculation_version == INDICATOR_VERSION,
            )
            .order_by(TechnicalIndicator.timestamp.desc())
            .limit(2)
        ).all()
    )
    price = db.scalar(
        select(StockPrice)
        .where(StockPrice.stock_id == stock.id, StockPrice.interval == "1d")
        .order_by(StockPrice.timestamp.desc())
        .limit(1)
    )
    benchmark = None
    if stock.sector:
        benchmark = db.scalar(
            select(SectorBenchmark)
            .where(SectorBenchmark.sector == stock.sector, SectorBenchmark.country == stock.country)
            .order_by(SectorBenchmark.calculation_date.desc())
            .limit(1)
        )
    return StoredContext(
        fundamentals=fundamentals,
        valuation=valuation,
        indicators=indicators,
        close=price.close if price is not None else None,
        close_at=price.timestamp if price is not None else None,
        volume=int(price.volume) if price is not None else None,
        benchmark=benchmark,
    )


def reading_for(metric: MetricDefinition, context: StoredContext, now: datetime) -> MetricReading:
    if metric.source == "valuation":
        row = context.valuation
        value = getattr(row, metric.key) if row is not None else None
        return _point(value, None, _benchmark(metric, context), row.provider_retrieved_at if row else None, row.source if row else None, _hours_stale(row.provider_retrieved_at if row else None, settings.fundamental_valuation_stale_hours, now))
    if metric.source == "fundamental":
        row = context.fundamentals[0] if context.fundamentals else None
        value = getattr(row, metric.key) if row is not None else None
        return _point(value, None, _benchmark(metric, context), row.provider_retrieved_at if row else None, row.source if row else None, _hours_stale(row.provider_retrieved_at if row else None, settings.fundamental_report_stale_hours, now))
    if metric.source == "derived_fundamental":
        row = context.fundamentals[0] if context.fundamentals else None
        value = _derived(metric.key, context.fundamentals)
        return _point(value, None, None, row.provider_retrieved_at if row else None, row.source if row else None, _hours_stale(row.provider_retrieved_at if row else None, settings.fundamental_report_stale_hours, now))
    if metric.source == "price":
        return _point(Decimal(context.volume) if context.volume is not None else None, None, None, context.close_at, "stock_prices", _price_stale(context.close_at, now))
    if metric.source == "derived_technical":
        value = _distance(metric.key, context)
        return _point(value, None, None, context.close_at, "technical_indicators", _price_stale(context.close_at, now))
    current = context.indicators[0] if context.indicators else None
    previous = context.indicators[1] if len(context.indicators) > 1 else None
    if metric.event_kind == "pair" and metric.pair is not None:
        return MetricReading(
            value=None,
            previous=None,
            pair_current=_pair(current, metric.pair),
            pair_previous=_pair(previous, metric.pair),
            reference=None,
            as_of=current.timestamp if current else None,
            source="technical_indicators",
            stale=_price_stale(current.timestamp if current else None, now) and _pair(current, metric.pair)[0] is not None,
            invalid=False,
        )
    value = getattr(current, metric.key) if current is not None else None
    prior = getattr(previous, metric.key) if previous is not None else None
    return _point(value, prior, None, current.timestamp if current else None, "technical_indicators", _price_stale(current.timestamp if current else None, now))


def _derived(key: str, rows: list[Fundamental]) -> Decimal | None:
    if not rows:
        return None
    latest = rows[0]
    if key == "cfo_to_net_profit":
        return cfo_to_net_profit(latest.operating_cash_flow, latest.net_income)
    if key == "revenue_cagr_3y":
        return annual_cagr(rows, 3)
    if key == "revenue_cagr_5y":
        return annual_cagr(rows, 5)
    return None


def _distance(key: str, context: StoredContext) -> Decimal | None:
    current = context.indicators[0] if context.indicators else None
    if current is None or context.close is None:
        return None
    extra = current.additional_indicators or {}
    bound_key = "week52_high" if key == "distance_from_high_percent" else "week52_low"
    bound = _decimal(extra.get(bound_key))
    return percent_distance(context.close, bound)


def _benchmark(metric: MetricDefinition, context: StoredContext) -> Decimal | None:
    if not metric.sector_benchmark or context.benchmark is None or not hasattr(context.benchmark, metric.key):
        return None
    value = getattr(context.benchmark, metric.key)
    return value if isinstance(value, Decimal) else None


def _pair(row: TechnicalIndicator | None, fields: tuple[str, str]) -> tuple[Decimal | None, Decimal | None]:
    if row is None:
        return (None, None)
    left = getattr(row, fields[0])
    right = getattr(row, fields[1])
    return (left if isinstance(left, Decimal) else None, right if isinstance(right, Decimal) else None)


def _point(
    value: Decimal | None,
    previous: Decimal | None,
    reference: Decimal | None,
    as_of: datetime | None,
    source: str | None,
    stale: bool,
) -> MetricReading:
    return MetricReading(value, previous, None, None, reference, as_of, source, bool(stale and value is not None), False)


def _hours_stale(retrieved: datetime | None, hours: int, now: datetime) -> bool:
    if retrieved is None:
        return False
    moment = retrieved if retrieved.tzinfo else retrieved.replace(tzinfo=UTC)
    return moment < now - timedelta(hours=hours)


def _price_stale(stamp: datetime | None, now: datetime) -> bool:
    if stamp is None:
        return False
    moment = stamp if stamp.tzinfo else stamp.replace(tzinfo=UTC)
    return moment.astimezone(IST).date() < now.astimezone(IST).date() - timedelta(days=STALE_DAYS)


def _decimal(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None

