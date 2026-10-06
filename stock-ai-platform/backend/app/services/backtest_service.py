"""Persist and execute user-owned backtests from stored daily bars.

The engine reads `stock_prices` only. It does not download bars, and it does
not treat a quote as a candle. Results stay in PostgreSQL.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from app.analysis.bars import Bar, prepare_bars
from app.analysis.config import DETECTOR_VERSION, INDICATOR_VERSION
from app.backtests import ENGINE_VERSION, PRICE_BASIS, SIZING_VERSION
from app.backtests.engine import Assumptions, simulate, session_date
from app.backtests.strategies import StrategyError, build_signals, get_strategy, list_strategies, validate_parameters, warmup_sessions
from app.core.config import settings
from app.data_providers.market_data.errors import NOT_FOUND, MarketDataError
from app.markets.time import IST
from app.models import BacktestEquityPoint, BacktestRun, BacktestTrade, Stock, StockPrice
from app.services.market_data_service import load_listing

logger = logging.getLogger(__name__)

DATA_SOURCE = "postgresql.stock_prices:1d"
LOCK_KEY = 81411015
STALE_AFTER = timedelta(minutes=15)
MESSAGES = {
    "unsupported_strategy": "That strategy is not available.",
    "unknown_parameter": "A strategy parameter is not supported.",
    "invalid_parameter": "A strategy parameter is outside the allowed range.",
    "invalid_range": "Choose a start date before the end date, no later than today, and at most three years apart.",
    "invalid_capital": "Initial capital must be between 1,000 and 100,000,000 INR.",
    "invalid_cost": "Brokerage must be from 0 to 5 percent, slippage from 0 to 100 basis points, and position size from 1 to 100 percent.",
    "duplicate_run": "A backtest is already queued or running.",
    "limit_reached": "The saved backtest limit has been reached. Delete an older run first.",
    "not_found": "That backtest was not found.",
}


class BacktestError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(MESSAGES.get(code, "The backtest could not be saved."))


def strategy_catalog() -> list[dict[str, object]]:
    rows = []
    for spec in list_strategies():
        rows.append(
            {
                "key": spec.key,
                "version": spec.version,
                "name": spec.name,
                "description": spec.description,
                "holds_overnight": spec.holds_overnight,
                "direction": spec.direction,
                "required_data": spec.required_data,
                "entry_rule": spec.entry_rule,
                "exit_rule": spec.exit_rule,
                "missing_data": spec.missing_data,
                "parameters": [
                    {
                        "name": item.name,
                        "label": item.label,
                        "kind": item.kind,
                        "minimum": item.minimum,
                        "maximum": item.maximum,
                        "default": item.default,
                        "description": item.description,
                    }
                    for item in spec.parameters
                ],
            }
        )
    return rows


def start_run(db: Session, user_id: UUID, payload: dict[str, object]) -> BacktestRun:
    stock = _stock(db, payload["stock_id"])
    spec = _strategy(str(payload["strategy_key"]), str(payload["strategy_version"]))
    params = _params(spec, payload.get("parameters") or {})
    assumptions = _assumptions(payload)
    start = payload["start_date"]
    end = payload["end_date"]
    _dates(start, end)
    _guard_capacity(db, user_id)
    run = BacktestRun(
        user_id=user_id,
        stock_id=stock.id,
        strategy_key=spec.key,
        strategy_version=spec.version,
        parameters=params,
        assumptions=_assumption_payload(assumptions),
        status="queued",
        requested_start=start,
        requested_end=end,
        initial_capital=assumptions.initial_capital,
        engine_version=ENGINE_VERSION,
        indicator_version=INDICATOR_VERSION,
        detector_version=DETECTOR_VERSION,
        data_source=DATA_SOURCE,
        price_basis=PRICE_BASIS,
        warnings=[],
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return execute_run(db, run.id)


def execute_run(db: Session, run_id: UUID) -> BacktestRun:
    run = db.get(BacktestRun, run_id, with_for_update=True)
    if run is None:
        raise BacktestError("not_found")
    if run.status in {"completed", "partial", "insufficient_data", "failed"}:
        return run
    if run.status == "running":
        return run
    run.status = "running"
    run.started_at = datetime.now(UTC)
    db.commit()
    try:
        outcome = _compute(db, run)
        _replace_children(db, run.id)
        for number, trade in enumerate(outcome.trades, start=1):
            db.add(
                BacktestTrade(
                    run_id=run.id,
                    trade_number=number,
                    signal_at=trade.signal_at,
                    entry_at=trade.entry_at,
                    exit_at=trade.exit_at,
                    entry_price=trade.entry_price,
                    exit_price=trade.exit_price,
                    shares=trade.shares,
                    entry_charges=trade.entry_charges,
                    exit_charges=trade.exit_charges,
                    slippage_cost=trade.slippage_cost,
                    exit_reason=trade.exit_reason,
                    pnl=trade.pnl,
                    return_percent=trade.return_percent,
                )
            )
        for mark in outcome.equity:
            db.add(
                BacktestEquityPoint(
                    run_id=run.id,
                    point_at=mark.timestamp,
                    equity=mark.equity,
                    drawdown_percent=mark.drawdown_percent,
                    cash=mark.cash,
                    shares=mark.shares,
                )
            )
        run.status = outcome.status
        run.summary = outcome.summary
        run.warnings = list(outcome.warnings)
        run.actual_start = outcome.actual_start
        run.actual_end = outcome.actual_end
        run.completed_at = datetime.now(UTC)
        run.error_detail = outcome.detail
        db.commit()
    except Exception:
        logger.exception("backtest run failed")
        db.rollback()
        failed = db.get(BacktestRun, run_id)
        if failed is not None and failed.status == "running":
            failed.status = "failed"
            failed.error_detail = "The backtest failed before results were saved."
            failed.completed_at = datetime.now(UTC)
            db.commit()
    refreshed = db.get(BacktestRun, run_id)
    if refreshed is None:
        raise BacktestError("not_found")
    return refreshed


def process_queued(db: Session) -> dict[str, int]:
    locked = db.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": LOCK_KEY}).scalar()
    if not locked:
        return {"processed": 0, "skipped": 1}
    try:
        cutoff = datetime.now(UTC) - STALE_AFTER
        stale = db.scalars(select(BacktestRun).where(BacktestRun.status == "running", BacktestRun.started_at < cutoff)).all()
        for row in stale:
            row.status = "queued"
        db.commit()
        run = db.scalar(select(BacktestRun).where(BacktestRun.status == "queued").order_by(BacktestRun.created_at).limit(1))
        if run is None:
            return {"processed": 0, "skipped": 0}
        execute_run(db, run.id)
        return {"processed": 1, "skipped": 0}
    finally:
        db.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK_KEY})
        db.commit()


def list_runs(db: Session, user_id: UUID, limit: int, offset: int) -> list[BacktestRun]:
    return list(
        db.scalars(
            select(BacktestRun)
            .where(BacktestRun.user_id == user_id)
            .order_by(BacktestRun.created_at.desc())
            .limit(limit)
            .offset(offset)
        ).all()
    )


def get_run(db: Session, user_id: UUID, run_id: UUID) -> BacktestRun:
    run = db.get(BacktestRun, run_id)
    if run is None or run.user_id != user_id:
        raise BacktestError("not_found")
    return run


def delete_run(db: Session, user_id: UUID, run_id: UUID) -> None:
    run = get_run(db, user_id, run_id)
    if run.status in {"queued", "running"}:
        raise BacktestError("duplicate_run")
    db.delete(run)
    db.commit()


def trades_for(db: Session, run: BacktestRun) -> list[BacktestTrade]:
    return list(db.scalars(select(BacktestTrade).where(BacktestTrade.run_id == run.id).order_by(BacktestTrade.trade_number)).all())


def equity_for(db: Session, run: BacktestRun) -> list[BacktestEquityPoint]:
    return list(db.scalars(select(BacktestEquityPoint).where(BacktestEquityPoint.run_id == run.id).order_by(BacktestEquityPoint.point_at)).all())


def symbol_for(db: Session, run: BacktestRun) -> tuple[str, str]:
    stock = db.get(Stock, run.stock_id)
    if stock is None:
        return "", ""
    return stock.symbol, stock.exchange


def _compute(db: Session, run: BacktestRun):
    spec = get_strategy(run.strategy_key, run.strategy_version)
    assumptions = _assumptions_from_stored(run.assumptions, run.initial_capital)
    raw = _load_bars(db, run.stock_id, run.requested_start, run.requested_end)
    clean, notes = prepare_bars(raw)
    in_range = [bar for bar in clean if run.requested_start <= session_date(bar.timestamp) <= run.requested_end]
    detail = None
    if not in_range:
        detail = "No stored daily bars fall inside the requested dates."
    elif (session_date(in_range[0].timestamp) - run.requested_start).days > 10:
        detail = "Stored daily bars do not reach the requested start. The period was not shortened."
    elif (run.requested_end - session_date(in_range[-1].timestamp)).days > 10:
        detail = "Stored daily bars do not reach the requested end. The period was not shortened."
    else:
        first_index = next(index for index, bar in enumerate(clean) if bar is in_range[0])
        needed = warmup_sessions(spec, {key: int(value) for key, value in run.parameters.items()})
        if first_index < needed:
            detail = "Not enough daily bars exist before the start date to compute this strategy without later data."
    if detail:
        from app.backtests.metrics import summarize

        summary = summarize(assumptions.initial_capital, [], [], 0, result_basis=assumptions.result_basis)
        warnings = [
            detail,
            "This is a historical simulation of one currently listed stock. It does not include delisted securities and it is not a forecast.",
            "No benchmark is shown because no historical index series is stored.",
        ]
        return _Outcome("insufficient_data", (), (), summary, tuple(warnings), None, None, detail)
    signals = build_signals(spec, {key: int(value) for key, value in run.parameters.items()}, clean)
    result = simulate(clean, signals, assumptions, run.requested_start, run.requested_end, notes)
    result.summary["sizing_version"] = SIZING_VERSION
    result.summary["engine_version"] = ENGINE_VERSION
    return _Outcome(result.status, result.trades, result.equity, result.summary, result.warnings, session_date(in_range[0].timestamp), session_date(in_range[-1].timestamp), None)


class _Outcome:
    def __init__(self, status, trades, equity, summary, warnings, actual_start, actual_end, detail) -> None:
        self.status = status
        self.trades = trades
        self.equity = equity
        self.summary = summary
        self.warnings = warnings
        self.actual_start = actual_start
        self.actual_end = actual_end
        self.detail = detail


def _load_bars(db: Session, stock_id: UUID, start: date, end: date) -> list[Bar]:
    window_start = datetime.combine(start - timedelta(days=400), time.min, tzinfo=IST)
    window_end = datetime.combine(end + timedelta(days=1), time.min, tzinfo=IST)
    rows = db.scalars(
        select(StockPrice)
        .where(
            StockPrice.stock_id == stock_id,
            StockPrice.interval == "1d",
            StockPrice.timestamp >= window_start,
            StockPrice.timestamp < window_end,
        )
        .order_by(StockPrice.timestamp)
    ).all()
    return [
        Bar(
            timestamp=row.timestamp,
            open=row.open,
            high=row.high,
            low=row.low,
            close=row.close,
            volume=int(row.volume),
        )
        for row in rows
    ]


def _replace_children(db: Session, run_id: UUID) -> None:
    db.execute(delete(BacktestTrade).where(BacktestTrade.run_id == run_id))
    db.execute(delete(BacktestEquityPoint).where(BacktestEquityPoint.run_id == run_id))


def _stock(db: Session, stock_id: object) -> Stock:
    try:
        return load_listing(db, stock_id)  # type: ignore[arg-type]
    except MarketDataError as exc:
        if exc.code == NOT_FOUND:
            raise BacktestError("not_found") from exc
        raise BacktestError("invalid_parameter") from exc


def _strategy(key: str, version: str):
    try:
        return get_strategy(key, version)
    except StrategyError as exc:
        raise BacktestError("unsupported_strategy") from exc


def _params(spec, raw: object) -> dict[str, int]:
    if not isinstance(raw, dict):
        raise BacktestError("invalid_parameter")
    try:
        return validate_parameters(spec, raw)
    except StrategyError as exc:
        code = str(exc)
        raise BacktestError(code if code in MESSAGES else "invalid_parameter") from exc


def _dates(start: object, end: object) -> None:
    if not isinstance(start, date) or not isinstance(end, date):
        raise BacktestError("invalid_range")
    today = datetime.now(UTC).astimezone(IST).date()
    if start >= end or end > today or (end - start).days > settings.backtest_max_calendar_days:
        raise BacktestError("invalid_range")


def _assumptions(payload: dict[str, object]) -> Assumptions:
    capital = _decimal(payload.get("initial_capital"), "invalid_capital")
    if capital < Decimal(1000) or capital > Decimal(100_000_000):
        raise BacktestError("invalid_capital")
    brokerage = _decimal(payload.get("brokerage_percent"), "invalid_cost")
    slippage = _decimal(payload.get("slippage_bps"), "invalid_cost")
    position = _decimal(payload.get("position_percent", 100), "invalid_cost")
    if brokerage < 0 or brokerage > 5 or slippage < 0 or slippage > 100 or position <= 0 or position > 100:
        raise BacktestError("invalid_cost")
    stop = _optional_decimal(payload.get("stop_loss_percent"), Decimal("0.1"), Decimal(50))
    target = _optional_decimal(payload.get("take_profit_percent"), Decimal("0.1"), Decimal(200))
    hold = payload.get("max_hold_sessions")
    if hold is not None and (isinstance(hold, bool) or not isinstance(hold, int) or hold < 1 or hold > 756):
        raise BacktestError("invalid_parameter")
    return Assumptions(
        _money(capital),
        _money(brokerage),
        _money(slippage),
        _money(position),
        None if stop is None else _money(stop),
        None if target is None else _money(target),
        hold if isinstance(hold, int) else None,
    )


def _assumptions_from_stored(raw: dict[str, object], capital: Decimal) -> Assumptions:
    return Assumptions(
        capital,
        Decimal(str(raw["brokerage_percent"])),
        Decimal(str(raw["slippage_bps"])),
        Decimal(str(raw["position_percent"])),
        None if raw.get("stop_loss_percent") is None else Decimal(str(raw["stop_loss_percent"])),
        None if raw.get("take_profit_percent") is None else Decimal(str(raw["take_profit_percent"])),
        None if raw.get("max_hold_sessions") is None else int(str(raw["max_hold_sessions"])),
    )


def _assumption_payload(assumptions: Assumptions) -> dict[str, object]:
    return {
        "initial_capital": format(assumptions.initial_capital, "f"),
        "brokerage_percent": format(assumptions.brokerage_percent, "f"),
        "slippage_bps": format(assumptions.slippage_bps, "f"),
        "position_percent": format(assumptions.position_percent, "f"),
        "stop_loss_percent": None if assumptions.stop_loss_percent is None else format(assumptions.stop_loss_percent, "f"),
        "take_profit_percent": None if assumptions.take_profit_percent is None else format(assumptions.take_profit_percent, "f"),
        "max_hold_sessions": assumptions.max_hold_sessions,
        "execution": "next_session_open",
        "sizing_version": SIZING_VERSION,
        "result_basis": assumptions.result_basis,
        "direction": "long_only",
        "share_rounding": "whole_shares",
    }


def _guard_capacity(db: Session, user_id: UUID) -> None:
    active = db.scalar(
        select(func.count()).select_from(BacktestRun).where(BacktestRun.user_id == user_id, BacktestRun.status.in_(("queued", "running")))
    )
    if active:
        raise BacktestError("duplicate_run")
    saved = db.scalar(select(func.count()).select_from(BacktestRun).where(BacktestRun.user_id == user_id))
    if saved is not None and int(saved) >= settings.backtest_max_runs:
        raise BacktestError("limit_reached")


def _decimal(value: object, code: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise BacktestError(code)
    try:
        return Decimal(str(value))
    except Exception as exc:
        raise BacktestError(code) from exc


def _optional_decimal(value: object, low: Decimal, high: Decimal) -> Decimal | None:
    if value is None:
        return None
    parsed = _decimal(value, "invalid_parameter")
    if parsed < low or parsed > high:
        raise BacktestError("invalid_parameter")
    return parsed


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
