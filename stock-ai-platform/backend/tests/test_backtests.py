"""Backtest signals, fills, costs, and ownership. Bars are fixtures."""

import uuid
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analysis.bars import Bar, prepare_bars
from app.analysis.patterns.common import PatternHit
from app.analysis.pivots import Pivot
from app.backtests.engine import Assumptions, shares_for_cash, simulate
from app.backtests.metrics import ClosedTrade, EquityPoint, summarize
from app.backtests.patterns import pattern_signals, signal_bar
from app.backtests.strategies import build_signals, get_strategy, validate_parameters
from app.core.database import get_db
from app.main import app
from app.markets.time import IST
from app.models import BacktestRun, BacktestTrade, Stock, StockPrice, User
from app.services.backtest_service import execute_run, process_queued
from tests.isolation import hide_committed_market_rows

PASSWORD = "Validpass1"
ORIGIN = "http://localhost:5173"


def _auth(client: TestClient) -> str:
    email = f"backtest-{uuid.uuid4().hex}@example.com"
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": PASSWORD, "full_name": "Backtest Tester"},
        headers={"Origin": ORIGIN},
    )
    assert response.status_code == 201, response.text
    return email


def _db() -> Session:
    return next(app.dependency_overrides[get_db]())


def _user(db: Session, email: str) -> User:
    user = db.scalar(select(User).where(User.email == email))
    assert user is not None
    return user


def _tcs(db: Session) -> Stock:
    stock = db.scalar(select(Stock).where(Stock.symbol == "TCS", Stock.exchange == "NSE"))
    assert stock is not None
    hide_committed_market_rows(db, stock.id)
    return stock


def _stamp(day: date) -> datetime:
    return datetime.combine(day, time(15, 30), tzinfo=IST)


def _series(start: date, closes: list[str]) -> list[Bar]:
    day = start
    bars: list[Bar] = []
    for close_text in closes:
        while day.weekday() >= 5:
            day += timedelta(days=1)
        close = Decimal(close_text)
        bars.append(Bar(_stamp(day), close, close + 1, close - 1, close, 1000))
        day += timedelta(days=1)
    return bars


def _assumptions(**overrides: object) -> Assumptions:
    values: dict[str, object] = {
        "initial_capital": Decimal("10000.00"),
        "brokerage_percent": Decimal("0.00"),
        "slippage_bps": Decimal("0.00"),
        "position_percent": Decimal("100.00"),
        "stop_loss_percent": None,
        "take_profit_percent": None,
        "max_hold_sessions": None,
    }
    values.update(overrides)
    return Assumptions(**values)  # type: ignore[arg-type]


def test_unknown_strategy_and_parameter_bounds() -> None:
    try:
        get_strategy("custom_code", "1")
        raise AssertionError("expected rejection")
    except ValueError as exc:
        assert str(exc) == "unsupported_strategy"
    spec = get_strategy("sma_crossover", "1")
    try:
        validate_parameters(spec, {"short_period": 50, "long_period": 20})
        raise AssertionError("expected rejection")
    except ValueError as exc:
        assert str(exc) == "invalid_parameter"


def test_indicator_signals_do_not_use_later_bars() -> None:
    bars = _series(date(2024, 1, 2), ["100"] * 60 + ["130"] * 20)
    spec = get_strategy("sma_crossover", "1")
    params = {"short_period": 20, "long_period": 50}
    full = build_signals(spec, params, bars)
    assert 60 in full and "enter" in full[60]
    for index in range(1, len(bars)):
        prefix = build_signals(spec, params, bars[: index + 1])
        earlier = build_signals(spec, params, bars[:index])
        assert prefix.get(index, set()) == full.get(index, set())
        assert index not in earlier


def test_entry_fills_at_the_next_session_open() -> None:
    bars = _series(date(2024, 1, 2), ["100", "100", "110", "120"])
    result = simulate(bars, {1: {"enter"}}, _assumptions(), date(2024, 1, 2), date(2024, 1, 8), [])
    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.signal_at == bars[1].timestamp
    assert trade.entry_at == bars[2].timestamp
    assert trade.entry_price == Decimal("110.0000")
    assert trade.entry_price != bars[1].close


def test_pattern_signal_waits_until_the_pivot_is_confirmed(monkeypatch) -> None:
    bars = _series(date(2024, 1, 2), ["10"] * 8)
    pivot = Pivot(1, bars[1].timestamp, 5, bars[5].timestamp, "low", Decimal("10"))
    hit = PatternHit(
        "double_bottom",
        "bullish_structure",
        "confirmed",
        1,
        2,
        (pivot,),
        {},
        {},
        2,
        "later",
        "later",
    )
    assert signal_bar(hit) == 5

    def fake(_prefix, _pivots, _config):  # type: ignore[no-untyped-def]
        if len(_prefix) < 6:
            return []
        return [hit]

    monkeypatch.setattr("app.backtests.patterns.detect_reversals", fake)
    assert pattern_signals(bars) == [(5, "enter")]
    assert pattern_signals(bars[:3]) == []


def test_whole_shares_costs_and_cash_limit() -> None:
    assumptions = _assumptions(brokerage_percent=Decimal("1.00"), slippage_bps=Decimal("10.00"))
    shares, charges = shares_for_cash(Decimal("10000"), Decimal("100.1000"), assumptions)
    assert shares == 98
    assert charges == Decimal("98.10")
    assert shares * Decimal("100.1000") + charges <= Decimal("10000")
    small = _assumptions()
    assert shares_for_cash(Decimal("150"), Decimal("100"), small)[0] == 1
    bars = _series(date(2024, 1, 2), ["100", "100", "100"])
    result = simulate(bars, {0: {"enter"}}, assumptions, date(2024, 1, 2), date(2024, 1, 4), [])
    trade = result.trades[0]
    assert trade.shares * trade.entry_price + trade.entry_charges <= Decimal("10000")
    assert trade.entry_price > bars[1].open
    assert trade.exit_price < bars[-1].close
    assert result.summary["result_basis"] == "net"


def test_ambiguous_candle_uses_the_stop_and_a_gap_uses_the_open() -> None:
    start = date(2024, 1, 2)
    first = Bar(_stamp(start), Decimal("100"), Decimal("101"), Decimal("99"), Decimal("100"), 1000)
    both = Bar(_stamp(start + timedelta(days=1)), Decimal("100"), Decimal("120"), Decimal("90"), Decimal("100"), 1000)
    assumptions = _assumptions(stop_loss_percent=Decimal("5.00"), take_profit_percent=Decimal("10.00"))
    result = simulate([first, both], {0: {"enter"}}, assumptions, start, start + timedelta(days=1), [])
    assert result.trades[0].exit_reason == "ambiguous_stop_and_target"
    assert result.trades[0].exit_price == Decimal("95.0000")
    held = Bar(_stamp(start + timedelta(days=1)), Decimal("100"), Decimal("101"), Decimal("99"), Decimal("100"), 1000)
    gap = Bar(_stamp(start + timedelta(days=2)), Decimal("90"), Decimal("92"), Decimal("88"), Decimal("91"), 1000)
    gapped = simulate([first, held, gap], {0: {"enter"}}, _assumptions(stop_loss_percent=Decimal("5.00")), start, start + timedelta(days=2), [])
    assert gapped.trades[0].exit_reason == "stop_loss"
    assert gapped.trades[0].exit_price == Decimal("90.0000")


def test_invalid_bars_are_excluded_and_missing_coverage_is_reported() -> None:
    start = date(2024, 1, 2)
    valid = Bar(_stamp(start), Decimal("10"), Decimal("11"), Decimal("9"), Decimal("10"), 100)
    invalid = Bar(_stamp(start + timedelta(days=1)), Decimal("10"), Decimal("8"), Decimal("9"), Decimal("10"), 100)
    clean, notes = prepare_bars([invalid, valid])
    assert clean == [valid]
    assert any("excluded" in note.lower() for note in notes)
    result = simulate(clean, {}, _assumptions(), start, start, notes)
    assert result.status == "partial"
    assert result.summary["benchmark"]["available"] is False


def test_metrics_avoid_undefined_ratios() -> None:
    points = [EquityPoint(Decimal("100"), 0), EquityPoint(Decimal("80"), 1), EquityPoint(Decimal("90"), 1)]
    winner = ClosedTrade(Decimal("10"), Decimal("5"), Decimal("100"), Decimal("110"), Decimal("1"), Decimal("0"))
    summary = summarize(Decimal("100"), points, [winner], 2, result_basis="gross")
    assert summary["profit_factor"] is None
    assert "undefined" in str(summary["profit_factor_reason"])
    assert summary["max_drawdown_percent"] == "20.000000"
    assert summary["annualized_return_percent"] is None
    empty = summarize(Decimal("100"), [], [], 0, result_basis="gross")
    assert empty["win_rate_percent"] is None
    assert empty["total_return_percent"] == "0.000000"


def test_repeated_simulation_matches() -> None:
    bars = _series(date(2024, 1, 2), ["100"] * 60 + ["130"] * 20)
    spec = get_strategy("sma_crossover", "1")
    params = {"short_period": 20, "long_period": 50}
    signals = build_signals(spec, params, bars)
    assumptions = _assumptions(brokerage_percent=Decimal("0.05"), slippage_bps=Decimal("5"))
    start = date(2024, 3, 20)
    end = date(2024, 4, 30)
    first = simulate(bars, signals, assumptions, start, end, [])
    second = simulate(bars, signals, assumptions, start, end, [])
    assert [(trade.entry_price, trade.exit_price, trade.shares, trade.pnl) for trade in first.trades] == [
        (trade.entry_price, trade.exit_price, trade.shares, trade.pnl) for trade in second.trades
    ]
    assert first.summary["final_equity"] == second.summary["final_equity"]


def _payload(stock: Stock, start: str, end: str) -> dict[str, object]:
    return {
        "stock_id": str(stock.id),
        "strategy_key": "sma_crossover",
        "strategy_version": "1",
        "parameters": {"short_period": 20, "long_period": 50},
        "start_date": start,
        "end_date": end,
        "initial_capital": "100000.00",
        "brokerage_percent": "0.10",
        "slippage_bps": "5",
        "position_percent": "100",
    }


def _store(db: Session, stock: Stock, closes: list[str]) -> tuple[date, date]:
    bars = _series(date(2024, 1, 2), closes)
    for bar in bars:
        db.add(
            StockPrice(
                stock_id=stock.id,
                interval="1d",
                timestamp=bar.timestamp,
                open=bar.open,
                high=bar.high,
                low=bar.low,
                close=bar.close,
                adjusted_close=None,
                volume=bar.volume,
            )
        )
    db.commit()
    return bars[0].timestamp.date(), bars[-1].timestamp.date()


def test_api_run_is_owned_and_reproducible(client: TestClient) -> None:
    email = _auth(client)
    db = _db()
    stock = _tcs(db)
    _store(db, stock, ["100"] * 60 + ["130"] * 20)
    created = client.post("/api/backtests/runs", json=_payload(stock, "2024-03-22", "2024-04-26"), headers={"Origin": ORIGIN})
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["status"] == "completed"
    assert body["summary"]["benchmark"]["available"] is False
    assert body["summary"]["result_basis"] == "net"
    assert "delisted" in " ".join(body["warnings"])
    trades = client.get(f"/api/backtests/runs/{body['id']}/trades")
    assert trades.status_code == 200
    assert trades.json()["results"]
    assert trades.json()["results"][0]["entry_at"] > trades.json()["results"][0]["signal_at"]
    equity = client.get(f"/api/backtests/runs/{body['id']}/equity")
    assert equity.status_code == 200
    assert equity.json()["results"]
    other = TestClient(app)
    _auth(other)
    assert other.get(f"/api/backtests/runs/{body['id']}").status_code == 404
    assert client.get("/api/backtests/strategies").status_code == 200
    rejected = client.post("/api/backtests/runs", json={**_payload(stock, "2024-03-22", "2024-04-26"), "strategy_key": "uploaded_script"}, headers={"Origin": ORIGIN})
    assert rejected.status_code == 422
    user = _user(db, email)
    assert db.scalar(select(func.count()).select_from(BacktestTrade).where(BacktestTrade.run_id == uuid.UUID(body["id"]))) >= 1
    missing = client.post("/api/backtests/runs", json=_payload(stock, "2020-01-02", "2020-06-30"), headers={"Origin": ORIGIN})
    assert missing.status_code == 200
    assert missing.json()["status"] == "insufficient_data"
    assert missing.json()["summary"]["completed_trades"] == 0
    running = db.get(BacktestRun, uuid.UUID(body["id"]))
    assert running is not None
    running.status = "running"
    running.started_at = datetime.now(UTC)
    running.completed_at = None
    db.commit()
    assert execute_run(db, running.id).status == "running"
    running.started_at = datetime.now(UTC) - timedelta(hours=1)
    db.commit()
    assert process_queued(db)["processed"] == 1
    assert process_queued(db)["processed"] == 0
    finished = db.get(BacktestRun, running.id)
    assert finished is not None
    assert finished.status == "completed"
    assert db.scalar(select(func.count()).select_from(BacktestTrade).where(BacktestTrade.run_id == finished.id)) >= 1
    assert user.id == finished.user_id
