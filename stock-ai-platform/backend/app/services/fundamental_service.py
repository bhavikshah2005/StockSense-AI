"""Load and store reported fundamentals and valuation snapshots.

PostgreSQL is the source of truth. The provider is called only when the stored
row is missing or older than the configured freshness window. A null filing
date means publication time is unknown: do not treat the result as known before
`provider_retrieved_at`.
"""

import logging
import threading
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.data_providers.fundamentals.base import FundamentalDataProvider, ReportedFundamental, ValuationReading
from app.data_providers.fundamentals.errors import TIMEOUT, UNAVAILABLE, FundamentalDataError
from app.markets.time import IST
from app.models import Fundamental, SectorBenchmark, Stock, ValuationSnapshot
from app.schemas.fundamentals import (
    FundamentalHistoryResponse,
    FundamentalMetadata,
    FundamentalMetrics,
    FundamentalPeriod,
    FundamentalReportResponse,
    SectorComparisonResponse,
    SectorMetric,
    StockRef,
    ValuationHistoryResponse,
    ValuationMetrics,
    ValuationResponse,
)
from app.services.fundamental_cache import FundamentalCache
from app.services.fundamental_math import annual_cagr, cfo_to_net_profit, fill_missing_growth
from app.services.market_data_service import load_listing

logger = logging.getLogger(__name__)

_guard = threading.Lock()
_locks: dict[str, threading.Lock] = {}

_REPORT_FIELDS = (
    "revenue",
    "revenue_growth",
    "ebitda",
    "ebitda_growth",
    "operating_profit",
    "net_income",
    "profit_growth",
    "eps",
    "eps_growth",
    "book_value_per_share",
    "roe",
    "roce",
    "gross_margin",
    "operating_margin",
    "net_margin",
    "debt_to_equity",
    "current_ratio",
    "interest_coverage",
    "free_cash_flow",
    "operating_cash_flow",
)
_VALUATION_FIELDS = (
    "market_price",
    "market_cap",
    "enterprise_value",
    "pe_ratio",
    "pb_ratio",
    "peg_ratio",
    "ev_to_ebitda",
    "ev_to_sales",
    "dividend_yield",
)


def get_latest_fundamentals(
    db: Session,
    stock_id: UUID,
    *,
    provider: FundamentalDataProvider,
    cache: FundamentalCache,
    ttl_seconds: int,
    stale_hours: int,
    now: datetime | None = None,
) -> FundamentalReportResponse:
    stock = load_listing(db, stock_id)
    key = f"fundamentals:{stock.id}:latest"
    cached = cache.get_report(key)
    if cached is not None:
        return cached
    with _lock(str(stock.id)):
        cached = cache.get_report(key)
        if cached is not None:
            return cached
        moment = now or datetime.now(UTC)
        _sync_reports(db, stock, provider, cache, stale_hours, moment)
        response = _latest_report(db, stock, moment, stale_hours)
        cache.put_report(key, response, ttl_seconds)
        return response


def get_fundamental_history(
    db: Session,
    stock_id: UUID,
    *,
    provider: FundamentalDataProvider,
    cache: FundamentalCache,
    ttl_seconds: int,
    stale_hours: int,
    start: date | None,
    end: date | None,
    period: str | None,
    limit: int,
    offset: int,
    now: datetime | None = None,
) -> FundamentalHistoryResponse:
    stock = load_listing(db, stock_id)
    key = f"fundamentals:{stock.id}:history:{start}:{end}:{period}:{limit}:{offset}"
    cached = cache.get_history(key)
    if cached is not None:
        return cached
    with _lock(str(stock.id)):
        cached = cache.get_history(key)
        if cached is not None:
            return cached
        moment = now or datetime.now(UTC)
        _sync_reports(db, stock, provider, cache, stale_hours, moment)
        all_rows = _report_rows(db, stock.id, None, None, None)
        filtered = _report_rows(db, stock.id, start, end, period)
        page = filtered[offset : offset + limit]
        response = FundamentalHistoryResponse(
            stock=_ref(stock),
            total=len(filtered),
            limit=limit,
            offset=offset,
            results=[_report_body(stock, row, all_rows, moment, stale_hours, as_of_row=True) for row in page],
        )
        cache.put_history(key, response, ttl_seconds)
        return response


def get_latest_valuation(
    db: Session,
    stock_id: UUID,
    *,
    provider: FundamentalDataProvider,
    cache: FundamentalCache,
    ttl_seconds: int,
    stale_hours: int,
    now: datetime | None = None,
) -> ValuationResponse:
    stock = load_listing(db, stock_id)
    key = f"valuation:{stock.id}:latest"
    cached = cache.get_valuation(key)
    if cached is not None:
        return cached
    with _lock(str(stock.id)):
        cached = cache.get_valuation(key)
        if cached is not None:
            return cached
        moment = now or datetime.now(UTC)
        _sync_valuations(db, stock, provider, cache, stale_hours, moment)
        response = _latest_valuation(db, stock, moment, stale_hours)
        cache.put_valuation(key, response, ttl_seconds)
        return response


def get_valuation_history(
    db: Session,
    stock_id: UUID,
    *,
    provider: FundamentalDataProvider,
    cache: FundamentalCache,
    ttl_seconds: int,
    stale_hours: int,
    start: date | None,
    end: date | None,
    limit: int,
    offset: int,
    now: datetime | None = None,
) -> ValuationHistoryResponse:
    stock = load_listing(db, stock_id)
    key = f"valuation:{stock.id}:history:{start}:{end}:{limit}:{offset}"
    cached = cache.get_valuation_history(key)
    if cached is not None:
        return cached
    with _lock(str(stock.id)):
        cached = cache.get_valuation_history(key)
        if cached is not None:
            return cached
        moment = now or datetime.now(UTC)
        _sync_valuations(db, stock, provider, cache, stale_hours, moment)
        rows = _valuation_rows(db, stock.id, start, end)
        page = rows[offset : offset + limit]
        response = ValuationHistoryResponse(
            stock=_ref(stock),
            total=len(rows),
            limit=limit,
            offset=offset,
            results=[_valuation_body(stock, row, moment, stale_hours) for row in page],
        )
        cache.put_valuation_history(key, response, ttl_seconds)
        return response


def get_sector_comparison(db: Session, stock_id: UUID) -> SectorComparisonResponse:
    """Compare stored stock metrics with a stored sector row. Missing benchmarks stay null."""
    stock = load_listing(db, stock_id)
    report = _newest_report(db, stock.id)
    valuation = _newest_valuation(db, stock.id)
    benchmark = None
    if stock.sector:
        benchmark = db.scalar(
            select(SectorBenchmark)
            .where(SectorBenchmark.sector == stock.sector, SectorBenchmark.country == stock.country)
            .order_by(SectorBenchmark.calculation_date.desc())
            .limit(1)
        )
    pairs = [
        ("pe_ratio", _value(valuation, "pe_ratio"), _value(benchmark, "pe_ratio")),
        ("pb_ratio", _value(valuation, "pb_ratio"), _value(benchmark, "pb_ratio")),
        ("dividend_yield", _value(valuation, "dividend_yield"), _value(benchmark, "dividend_yield")),
        ("roe", _value(report, "roe"), _value(benchmark, "roe")),
        ("roce", _value(report, "roce"), _value(benchmark, "roce")),
        ("net_margin", _value(report, "net_margin"), _value(benchmark, "net_margin")),
        ("revenue_growth", _value(report, "revenue_growth"), _value(benchmark, "revenue_growth")),
        ("debt_to_equity", _value(report, "debt_to_equity"), _value(benchmark, "debt_to_equity")),
    ]
    return SectorComparisonResponse(
        stock=_ref(stock),
        sector=stock.sector,
        calculation_date=benchmark.calculation_date if benchmark is not None else None,
        source=benchmark.source if benchmark is not None else None,
        methodology=benchmark.methodology if benchmark is not None else None,
        metrics=[
            SectorMetric(
                metric=name,
                stock_value=stock_value,
                benchmark_value=benchmark_value,
                difference=None
                if stock_value is None or benchmark_value is None
                else (stock_value - benchmark_value).quantize(Decimal("0.000001")),
            )
            for name, stock_value, benchmark_value in pairs
        ],
        benchmark_available=benchmark is not None,
    )


def _sync_reports(
    db: Session,
    stock: Stock,
    provider: FundamentalDataProvider,
    cache: FundamentalCache,
    stale_hours: int,
    now: datetime,
) -> None:
    latest = _newest_report(db, stock.id)
    if latest is not None and not _is_stale(latest.provider_retrieved_at, stale_hours, now):
        return
    try:
        reports = provider.get_fundamental_history(
            symbol=stock.symbol,
            exchange=stock.exchange,
            currency=stock.currency,
            country=stock.country,
        )
    except FundamentalDataError as exc:
        _log(provider, exc.code)
        if latest is not None:
            return
        raise
    except TimeoutError:
        _log(provider, TIMEOUT)
        if latest is None:
            raise FundamentalDataError(TIMEOUT) from None
        return
    except OSError:
        _log(provider, UNAVAILABLE)
        if latest is None:
            raise FundamentalDataError(UNAVAILABLE) from None
        return
    if _store_reports(db, stock, provider.name, reports):
        cache.invalidate_stock(stock.id)


def _sync_valuations(
    db: Session,
    stock: Stock,
    provider: FundamentalDataProvider,
    cache: FundamentalCache,
    stale_hours: int,
    now: datetime,
) -> None:
    latest = _newest_valuation(db, stock.id)
    if latest is not None and not _is_stale(latest.provider_retrieved_at, stale_hours, now):
        return
    try:
        readings = provider.get_valuation_history(
            symbol=stock.symbol,
            exchange=stock.exchange,
            currency=stock.currency,
            country=stock.country,
        )
    except FundamentalDataError as exc:
        _log(provider, exc.code)
        if latest is not None:
            return
        raise
    except TimeoutError:
        _log(provider, TIMEOUT)
        if latest is None:
            raise FundamentalDataError(TIMEOUT) from None
        return
    except OSError:
        _log(provider, UNAVAILABLE)
        if latest is None:
            raise FundamentalDataError(UNAVAILABLE) from None
        return
    if _store_valuations(db, stock, provider.name, readings):
        cache.invalidate_stock(stock.id)


def _store_reports(db: Session, stock: Stock, source: str, reports: list[ReportedFundamental]) -> int:
    written = 0
    try:
        for report in sorted(reports, key=lambda item: item.period_end):
            if report.currency != stock.currency:
                logger.warning("fundamental currency mismatch provider=%s", source)
                continue
            if not _has_any(report, _REPORT_FIELDS):
                continue
            row = Fundamental(
                stock_id=stock.id,
                report_date=report.period_end,
                fiscal_period=report.fiscal_period,
                fiscal_period_type=report.fiscal_period_type,
                filing_date=report.filing_date,
                currency=report.currency,
                source=source,
            )
            for field in _REPORT_FIELDS:
                setattr(row, field, getattr(report, field))
            row.provider_retrieved_at = report.provider_retrieved_at
            fill_missing_growth(row, _previous_report(db, stock.id, report.fiscal_period_type, report.period_end))
            _upsert_report(db, row)
            written += 1
        if written:
            db.commit()
    except Exception:
        db.rollback()
        raise
    return written


def _store_valuations(db: Session, stock: Stock, source: str, readings: list[ValuationReading]) -> int:
    written = 0
    try:
        for reading in readings:
            if reading.currency != stock.currency:
                logger.warning("valuation currency mismatch provider=%s", source)
                continue
            if not _has_any(reading, _VALUATION_FIELDS):
                continue
            values: dict[str, object] = {
                "stock_id": stock.id,
                "snapshot_at": reading.snapshot_at,
                "currency": reading.currency,
                "source": source,
                "provider_retrieved_at": reading.provider_retrieved_at,
            }
            for field in _VALUATION_FIELDS:
                values[field] = getattr(reading, field)
            statement = pg_insert(ValuationSnapshot).values(values)
            statement = statement.on_conflict_do_update(
                index_elements=["stock_id", "snapshot_at", "source"],
                set_={
                    field: func.coalesce(getattr(statement.excluded, field), getattr(ValuationSnapshot, field))
                    for field in _VALUATION_FIELDS
                }
                | {
                    "provider_retrieved_at": statement.excluded.provider_retrieved_at,
                    "currency": statement.excluded.currency,
                    "updated_at": func.now(),
                },
            )
            db.execute(statement)
            written += 1
        if written:
            db.commit()
    except Exception:
        db.rollback()
        raise
    return written


def _upsert_report(db: Session, row: Fundamental) -> None:
    values: dict[str, object] = {
        "stock_id": row.stock_id,
        "report_date": row.report_date,
        "fiscal_period": row.fiscal_period,
        "fiscal_period_type": row.fiscal_period_type,
        "filing_date": row.filing_date,
        "currency": row.currency,
        "source": row.source,
        "provider_retrieved_at": row.provider_retrieved_at,
    }
    for field in _REPORT_FIELDS:
        values[field] = getattr(row, field)
    statement = pg_insert(Fundamental).values(values)
    preserved = {
        field: func.coalesce(getattr(statement.excluded, field), getattr(Fundamental, field)) for field in _REPORT_FIELDS
    }
    preserved["filing_date"] = func.coalesce(statement.excluded.filing_date, Fundamental.filing_date)
    preserved["provider_retrieved_at"] = statement.excluded.provider_retrieved_at
    preserved["fiscal_period_type"] = statement.excluded.fiscal_period_type
    preserved["updated_at"] = func.now()
    statement = statement.on_conflict_do_update(
        index_elements=["stock_id", "report_date", "fiscal_period", "source"],
        set_=preserved,
    )
    db.execute(statement)


def _latest_report(db: Session, stock: Stock, now: datetime, stale_hours: int) -> FundamentalReportResponse:
    row = _newest_report(db, stock.id)
    if row is None:
        return _empty_report(stock)
    rows = _report_rows(db, stock.id, None, None, None)
    return _report_body(stock, row, rows, now, stale_hours, as_of_row=False)


_ANNUAL_FALLBACK = (
    "roe",
    "roce",
    "gross_margin",
    "debt_to_equity",
    "current_ratio",
    "free_cash_flow",
    "operating_cash_flow",
)


def _report_body(
    stock: Stock,
    row: Fundamental,
    rows: list[Fundamental],
    now: datetime,
    stale_hours: int,
    *,
    as_of_row: bool,
) -> FundamentalReportResponse:
    basis = _known_as_of(rows, row) if as_of_row else rows
    annual = _latest_annual(basis, row)
    borrowed = annual.fiscal_period if annual is not None and _uses_annual(row, annual) else None
    cash_flow = row.operating_cash_flow if row.operating_cash_flow is not None else _annual_value(annual, "operating_cash_flow")
    cash_profit = row.net_income if row.operating_cash_flow is not None else _annual_value(annual, "net_income")
    metrics = FundamentalMetrics(
        revenue=row.revenue,
        revenue_growth=row.revenue_growth,
        ebitda=row.ebitda,
        ebitda_growth=row.ebitda_growth,
        operating_profit=row.operating_profit,
        net_income=row.net_income,
        profit_growth=row.profit_growth,
        eps=row.eps,
        eps_growth=row.eps_growth,
        book_value_per_share=row.book_value_per_share,
        roe=_filled(row, annual, "roe"),
        roce=_filled(row, annual, "roce"),
        gross_margin=_filled(row, annual, "gross_margin"),
        operating_margin=row.operating_margin,
        net_margin=row.net_margin,
        debt_to_equity=_filled(row, annual, "debt_to_equity"),
        current_ratio=_filled(row, annual, "current_ratio"),
        interest_coverage=row.interest_coverage,
        free_cash_flow=_filled(row, annual, "free_cash_flow"),
        operating_cash_flow=cash_flow,
        cfo_to_net_profit=cfo_to_net_profit(cash_flow, cash_profit),
        revenue_cagr_3y=annual_cagr(basis, 3),
        revenue_cagr_5y=annual_cagr(basis, 5),
    )
    return FundamentalReportResponse(
        stock=_ref(stock),
        data=metrics,
        period=FundamentalPeriod(
            fiscal_period=row.fiscal_period,
            fiscal_period_type=row.fiscal_period_type,
            report_date=row.report_date,
            filing_date=row.filing_date,
        ),
        metadata=_meta(
            row.currency,
            row.source,
            row.provider_retrieved_at,
            _is_stale(row.provider_retrieved_at, stale_hours, now),
            _any_metric(metrics),
            row.filing_date is not None,
            borrowed,
        ),
    )


def _latest_valuation(db: Session, stock: Stock, now: datetime, stale_hours: int) -> ValuationResponse:
    row = _newest_valuation(db, stock.id)
    if row is None:
        return _empty_valuation(stock)
    return _valuation_body(stock, row, now, stale_hours)


def _valuation_body(stock: Stock, row: ValuationSnapshot, now: datetime, stale_hours: int) -> ValuationResponse:
    metrics = ValuationMetrics(
        market_price=row.market_price,
        market_cap=row.market_cap,
        enterprise_value=row.enterprise_value,
        pe_ratio=row.pe_ratio,
        pb_ratio=row.pb_ratio,
        peg_ratio=row.peg_ratio,
        ev_to_ebitda=row.ev_to_ebitda,
        ev_to_sales=row.ev_to_sales,
        dividend_yield=row.dividend_yield,
    )
    return ValuationResponse(
        stock=_ref(stock),
        data=metrics,
        snapshot_at=row.snapshot_at,
        metadata=_meta(
            row.currency,
            row.source,
            row.provider_retrieved_at,
            _is_stale(row.provider_retrieved_at, stale_hours, now),
            _any_metric(metrics),
            False,
        ),
    )


def _empty_report(stock: Stock) -> FundamentalReportResponse:
    return FundamentalReportResponse(
        stock=_ref(stock),
        data=FundamentalMetrics(),
        period=None,
        metadata=_meta(stock.currency, None, None, False, False, False),
    )


def _empty_valuation(stock: Stock) -> ValuationResponse:
    return ValuationResponse(
        stock=_ref(stock),
        data=ValuationMetrics(),
        snapshot_at=None,
        metadata=_meta(stock.currency, None, None, False, False, False),
    )


def _newest_report(db: Session, stock_id: UUID) -> Fundamental | None:
    return db.scalar(
        select(Fundamental).where(Fundamental.stock_id == stock_id).order_by(Fundamental.report_date.desc()).limit(1)
    )


def _newest_valuation(db: Session, stock_id: UUID) -> ValuationSnapshot | None:
    return db.scalar(
        select(ValuationSnapshot)
        .where(ValuationSnapshot.stock_id == stock_id)
        .order_by(ValuationSnapshot.snapshot_at.desc())
        .limit(1)
    )


def _previous_report(db: Session, stock_id: UUID, period_type: str, period_end: date) -> Fundamental | None:
    return db.scalar(
        select(Fundamental)
        .where(
            Fundamental.stock_id == stock_id,
            Fundamental.fiscal_period_type == period_type,
            Fundamental.report_date < period_end,
        )
        .order_by(Fundamental.report_date.desc())
        .limit(1)
    )


def _report_rows(
    db: Session,
    stock_id: UUID,
    start: date | None,
    end: date | None,
    period: str | None,
) -> list[Fundamental]:
    statement = select(Fundamental).where(Fundamental.stock_id == stock_id)
    if start is not None:
        statement = statement.where(Fundamental.report_date >= start)
    if end is not None:
        statement = statement.where(Fundamental.report_date <= end)
    if period is not None:
        statement = statement.where(Fundamental.fiscal_period_type == period)
    return list(db.scalars(statement.order_by(Fundamental.report_date)).all())


def _valuation_rows(db: Session, stock_id: UUID, start: date | None, end: date | None) -> list[ValuationSnapshot]:
    statement = select(ValuationSnapshot).where(ValuationSnapshot.stock_id == stock_id)
    if start is not None:
        statement = statement.where(ValuationSnapshot.snapshot_at >= datetime.combine(start, datetime.min.time(), tzinfo=IST))
    if end is not None:
        statement = statement.where(
            ValuationSnapshot.snapshot_at < datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=IST)
        )
    return list(db.scalars(statement.order_by(ValuationSnapshot.snapshot_at)).all())


def _known_as_of(rows: list[Fundamental], current: Fundamental) -> list[Fundamental]:
    """Reports that do not post-date this row. A missing filing date cannot prove an earlier publication."""
    selected: list[Fundamental] = []
    for item in rows:
        if item.report_date > current.report_date:
            continue
        if current.filing_date is not None and item.filing_date is not None and item.filing_date > current.filing_date:
            continue
        selected.append(item)
    return selected


def _is_stale(retrieved: datetime | None, stale_hours: int, now: datetime) -> bool:
    if retrieved is None:
        return True
    return retrieved < now - timedelta(hours=stale_hours)


def _has_any(item: object, fields: tuple[str, ...]) -> bool:
    return any(getattr(item, field) is not None for field in fields)


def _any_metric(metrics: FundamentalMetrics | ValuationMetrics) -> bool:
    return any(value is not None for value in metrics.model_dump().values())


def _value(row: object | None, field: str) -> Decimal | None:
    if row is None:
        return None
    value = getattr(row, field, None)
    return value if isinstance(value, Decimal) else None


def _ref(stock: Stock) -> StockRef:
    return StockRef(id=stock.id, symbol=stock.symbol, exchange=stock.exchange, company_name=stock.company_name)


def _latest_annual(rows: list[Fundamental], current: Fundamental) -> Fundamental | None:
    """Latest annual report on or before this period. A quarterly filing often omits the balance sheet."""
    if current.fiscal_period_type == "annual":
        return None
    annual = [row for row in rows if row.fiscal_period_type == "annual" and row.report_date <= current.report_date]
    if not annual:
        return None
    return max(annual, key=lambda row: row.report_date)


def _filled(current: Fundamental, annual: Fundamental | None, field: str) -> Decimal | None:
    value = getattr(current, field)
    if value is not None or annual is None:
        return value
    borrowed = getattr(annual, field)
    return borrowed if isinstance(borrowed, Decimal) else None


def _annual_value(annual: Fundamental | None, field: str) -> Decimal | None:
    if annual is None:
        return None
    value = getattr(annual, field)
    return value if isinstance(value, Decimal) else None


def _uses_annual(current: Fundamental, annual: Fundamental) -> bool:
    if current.operating_cash_flow is None and annual.operating_cash_flow is not None:
        return True
    return any(getattr(current, field) is None and getattr(annual, field) is not None for field in _ANNUAL_FALLBACK)


def _meta(
    currency: str,
    source: str | None,
    retrieved: datetime | None,
    stale: bool,
    available: bool,
    filing_known: bool,
    supplemented_from_period: str | None = None,
) -> FundamentalMetadata:
    return FundamentalMetadata(
        currency=currency,
        source=source,
        data_as_of=retrieved,
        is_available=available,
        is_stale=stale,
        filing_date_known=filing_known,
        supplemented_from_period=supplemented_from_period,
    )


def _log(provider: FundamentalDataProvider, code: str) -> None:
    logger.warning("fundamental provider error code=%s provider=%s", code, provider.name)


def _lock(key: str) -> threading.Lock:
    with _guard:
        lock = _locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _locks[key] = lock
        return lock
