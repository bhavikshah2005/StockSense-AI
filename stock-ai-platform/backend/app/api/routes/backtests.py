"""Authenticated backtest routes. Ownership comes from the session."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.rate_limit import RateLimiter, get_rate_limiter
from app.models import User
from app.schemas.backtest import (
    CompareResponse,
    EquityPointResponse,
    EquityResponse,
    RunCreate,
    RunListResponse,
    RunResponse,
    StrategyResponse,
    TradeListResponse,
    TradeResponse,
)
from app.services.backtest_service import BacktestError, delete_run, equity_for, get_run, list_runs, start_run, strategy_catalog, symbol_for, trades_for

router = APIRouter(prefix="/api/backtests", tags=["backtests"])

HTTP = {
    "not_found": 404,
    "duplicate_run": 409,
    "unsupported_strategy": 422,
    "unknown_parameter": 422,
    "invalid_parameter": 422,
    "invalid_range": 422,
    "invalid_capital": 422,
    "invalid_cost": 422,
    "limit_reached": 422,
}


@router.get("/strategies", response_model=list[StrategyResponse])
def strategies(_user: User = Depends(get_current_user)) -> list[StrategyResponse]:
    return [StrategyResponse.model_validate(row) for row in strategy_catalog()]


@router.post("/runs", response_model=RunResponse)
def create_run(
    payload: RunCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limiter: RateLimiter = Depends(get_rate_limiter),
) -> RunResponse:
    allowed = limiter.hit(f"backtest:{user.id}", settings.backtest_runs_per_hour, 3600)
    if not allowed:
        raise HTTPException(status_code=429, detail="Too many backtests. Try again later.")
    try:
        run = start_run(db, user.id, payload.model_dump())
    except BacktestError as exc:
        raise _http(exc) from exc
    return _run(db, run)


@router.get("/runs", response_model=RunListResponse)
def runs(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
) -> RunListResponse:
    rows = list_runs(db, user.id, limit, offset)
    return RunListResponse(results=[_run(db, row) for row in rows], limit=limit, offset=offset)


@router.get("/compare", response_model=CompareResponse)
def compare(
    left: UUID,
    right: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CompareResponse:
    try:
        first = get_run(db, user.id, left)
        second = get_run(db, user.id, right)
    except BacktestError as exc:
        raise _http(exc) from exc
    comparable, note = _compare_note(first, second)
    return CompareResponse(left=_run(db, first), right=_run(db, second), comparable=comparable, note=note)


@router.get("/runs/{run_id}", response_model=RunResponse)
def read_run(run_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> RunResponse:
    try:
        run = get_run(db, user.id, run_id)
    except BacktestError as exc:
        raise _http(exc) from exc
    return _run(db, run)


@router.get("/runs/{run_id}/trades", response_model=TradeListResponse)
def read_trades(run_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> TradeListResponse:
    try:
        run = get_run(db, user.id, run_id)
    except BacktestError as exc:
        raise _http(exc) from exc
    return TradeListResponse(
        results=[
            TradeResponse(
                trade_number=row.trade_number,
                signal_at=row.signal_at,
                entry_at=row.entry_at,
                exit_at=row.exit_at,
                entry_price=format(row.entry_price, "f"),
                exit_price=format(row.exit_price, "f"),
                shares=row.shares,
                entry_charges=format(row.entry_charges, "f"),
                exit_charges=format(row.exit_charges, "f"),
                slippage_cost=format(row.slippage_cost, "f"),
                exit_reason=row.exit_reason,
                pnl=format(row.pnl, "f"),
                return_percent=None if row.return_percent is None else format(row.return_percent, "f"),
            )
            for row in trades_for(db, run)
        ]
    )


@router.get("/runs/{run_id}/equity", response_model=EquityResponse)
def read_equity(run_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> EquityResponse:
    try:
        run = get_run(db, user.id, run_id)
    except BacktestError as exc:
        raise _http(exc) from exc
    return EquityResponse(
        results=[
            EquityPointResponse(
                point_at=row.point_at,
                equity=format(row.equity, "f"),
                drawdown_percent=format(row.drawdown_percent, "f"),
                cash=format(row.cash, "f"),
                shares=row.shares,
            )
            for row in equity_for(db, run)
        ]
    )


@router.delete("/runs/{run_id}", status_code=204)
def remove_run(run_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    try:
        delete_run(db, user.id, run_id)
    except BacktestError as exc:
        raise _http(exc) from exc
    return Response(status_code=204)


def _run(db: Session, run) -> RunResponse:
    symbol, exchange = symbol_for(db, run)
    return RunResponse(
        id=run.id,
        stock_id=run.stock_id,
        symbol=symbol,
        exchange=exchange,
        strategy_key=run.strategy_key,
        strategy_version=run.strategy_version,
        parameters=run.parameters,
        assumptions=run.assumptions,
        status=run.status,
        requested_start=run.requested_start,
        requested_end=run.requested_end,
        actual_start=run.actual_start,
        actual_end=run.actual_end,
        initial_capital=format(run.initial_capital, "f"),
        engine_version=run.engine_version,
        indicator_version=run.indicator_version,
        detector_version=run.detector_version,
        data_source=run.data_source,
        price_basis=run.price_basis,
        summary=run.summary,
        warnings=list(run.warnings or []),
        error_detail=run.error_detail,
        created_at=run.created_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
    )


def _compare_note(left, right) -> tuple[bool, str]:
    finished = left.status in {"completed", "partial"} and right.status in {"completed", "partial"}
    if not finished:
        return False, "Both runs need saved results before they can be viewed together."
    overlap = not (left.requested_end < right.requested_start or right.requested_end < left.requested_start)
    if left.stock_id != right.stock_id or not overlap:
        return False, "These runs use different stocks or non-overlapping dates, so they are shown separately."
    if left.assumptions != right.assumptions or left.strategy_key != right.strategy_key:
        return False, "These runs overlap, but the strategy or the capital, cost, and slippage assumptions differ."
    return True, "These runs share a stock, a strategy, an overlapping period, and the same cost assumptions. This is not a ranking and it is not a forecast."


def _http(exc: BacktestError) -> HTTPException:
    return HTTPException(status_code=HTTP.get(exc.code, 422), detail=str(exc))
