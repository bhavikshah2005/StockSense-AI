"""Long-only daily simulation.

End-of-day signals fill at the next stored session's open. A stop and a target
touched in the same candle fill at the stop. This is not a broker and it does
not model shorts, margin, or intraday books.

Position size uses available cash and whole shares. It is separate from the
portfolio planner, which does not replay historical bars.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

from app.analysis.bars import Bar
from app.backtests import ENGINE_VERSION, EXECUTION_CONVENTION, PRICE_BASIS, SIZING_VERSION
from app.backtests.metrics import ClosedTrade, EquityPoint, summarize
from app.markets.time import IST

MONEY = Decimal("0.01")
PRICE = Decimal("0.0001")
BPS = Decimal("10000")


@dataclass(frozen=True)
class Assumptions:
    initial_capital: Decimal
    brokerage_percent: Decimal
    slippage_bps: Decimal
    position_percent: Decimal
    stop_loss_percent: Decimal | None
    take_profit_percent: Decimal | None
    max_hold_sessions: int | None

    @property
    def result_basis(self) -> str:
        if self.brokerage_percent == 0 and self.slippage_bps == 0:
            return "gross"
        return "net"


@dataclass(frozen=True)
class SimulatedTrade:
    signal_at: datetime
    entry_at: datetime
    exit_at: datetime
    entry_price: Decimal
    exit_price: Decimal
    shares: int
    entry_charges: Decimal
    exit_charges: Decimal
    slippage_cost: Decimal
    exit_reason: str
    pnl: Decimal
    return_percent: Decimal | None


@dataclass
class _Position:
    signal_at: datetime
    entry_at: datetime
    entry_index: int
    entry_price: Decimal
    raw_entry: Decimal
    shares: int
    entry_charges: Decimal
    entry_slippage: Decimal


@dataclass(frozen=True)
class EquityMark:
    timestamp: datetime
    equity: Decimal
    drawdown_percent: Decimal
    cash: Decimal
    shares: int


@dataclass(frozen=True)
class Simulation:
    status: str
    trades: tuple[SimulatedTrade, ...]
    equity: tuple[EquityMark, ...]
    summary: dict[str, object]
    warnings: tuple[str, ...]
    engine_version: str
    execution: str
    price_basis: str
    sizing_version: str


def session_date(moment: datetime) -> date:
    return moment.astimezone(IST).date()


def simulate(
    bars: list[Bar],
    signals: dict[int, set[str]],
    assumptions: Assumptions,
    start: date,
    end: date,
    notes: list[str],
) -> Simulation:
    warnings = list(notes)
    warnings.extend(_standing_warnings(assumptions))
    warnings.extend(_gap_warnings(bars, start, end))
    cash = _money(assumptions.initial_capital)
    position: _Position | None = None
    pending: tuple[str, str] | None = None
    trades: list[SimulatedTrade] = []
    marks: list[EquityMark] = []
    peak = cash
    test_indexes = [index for index, bar in enumerate(bars) if start <= session_date(bar.timestamp) <= end]
    if not test_indexes:
        return _empty("insufficient_data", assumptions, warnings + ["No stored daily bars fall inside the requested dates."])
    last_index = test_indexes[-1]
    skipped = False
    for index, bar in enumerate(bars):
        in_window = start <= session_date(bar.timestamp) <= end
        if in_window and pending is not None and pending[0] == "enter" and position is None:
            position = _buy(bar, cash, assumptions, signal_at=_signal_time(bars, index), entry_index=index)
            if position is None:
                skipped = True
            else:
                cash = _money(cash - position.shares * position.entry_price - position.entry_charges)
            pending = None
        elif in_window and pending is not None and pending[0] == "exit" and position is not None:
            trades.append(_sell(position, bar, bar.open, pending[1], assumptions))
            cash = _after_sale(cash, trades[-1])
            position = None
            pending = None
        if in_window and position is not None:
            exit_fill = _risk_exit(bar, position, assumptions)
            if exit_fill is not None:
                price, reason = exit_fill
                trades.append(_sell(position, bar, price, reason, assumptions))
                cash = _after_sale(cash, trades[-1])
                position = None
                pending = None
        if in_window and index == last_index and position is not None:
            trades.append(_sell(position, bar, bar.close, "end_of_test", assumptions))
            cash = _after_sale(cash, trades[-1])
            position = None
            pending = None
        if in_window:
            equity = _money(cash + (position.shares * bar.close if position else Decimal(0)))
            if equity > peak:
                peak = equity
            drawdown = Decimal(0) if peak <= 0 else (peak - equity) / peak * Decimal(100)
            marks.append(EquityMark(bar.timestamp, equity, _money(drawdown), cash, position.shares if position else 0))
        actions = signals.get(index, set())
        if index >= last_index:
            continue
        if position is not None and "exit" in actions:
            pending = ("exit", "opposite_signal")
        elif position is None and (pending is None or pending[0] != "exit") and "enter" in actions:
            pending = ("enter", "signal")
        elif position is not None and assumptions.max_hold_sessions is not None:
            held = index - position.entry_index + 1
            if held >= assumptions.max_hold_sessions:
                pending = ("exit", "max_hold")
    if skipped:
        warnings.append("At least one entry was skipped because the cash could not buy one whole share after costs.")
    if pending is not None and pending[0] == "enter":
        warnings.append("A signal on the final session was not filled because no later stored session exists.")
    closed = [
        ClosedTrade(
            trade.pnl,
            trade.return_percent,
            _money(trade.entry_price * trade.shares),
            _money(trade.exit_price * trade.shares),
            _money(trade.entry_charges + trade.exit_charges),
            trade.slippage_cost,
        )
        for trade in trades
    ]
    points = [EquityPoint(mark.equity, mark.shares) for mark in marks]
    in_market = sum(1 for mark in marks if mark.shares > 0)
    summary = summarize(assumptions.initial_capital, points, closed, in_market, result_basis=assumptions.result_basis)
    status = "partial" if any("excluded" in note.lower() or "duplicate" in note.lower() for note in notes) else "completed"
    return Simulation(status, tuple(trades), tuple(marks), summary, tuple(dict.fromkeys(warnings)), ENGINE_VERSION, EXECUTION_CONVENTION, PRICE_BASIS, SIZING_VERSION)


def shares_for_cash(cash: Decimal, price: Decimal, assumptions: Assumptions) -> tuple[int, Decimal]:
    """Whole shares affordable with cash, brokerage, and buy slippage. Returns shares and charge."""
    if price <= 0 or cash <= 0:
        return 0, Decimal(0)
    budget = cash * assumptions.position_percent / Decimal(100)
    unit = price * (Decimal(1) + assumptions.brokerage_percent / Decimal(100))
    if unit <= 0:
        return 0, Decimal(0)
    shares = int(budget // unit)
    while shares > 0:
        notional = price * shares
        charges = _money(notional * assumptions.brokerage_percent / Decimal(100))
        if notional + charges <= cash:
            return shares, charges
        shares -= 1
    return 0, Decimal(0)


def _buy(bar: Bar, cash: Decimal, assumptions: Assumptions, signal_at: datetime, entry_index: int) -> _Position | None:
    raw = bar.open
    price = _price(raw * (Decimal(1) + assumptions.slippage_bps / BPS))
    shares, charges = shares_for_cash(cash, price, assumptions)
    if shares < 1:
        return None
    return _Position(signal_at, bar.timestamp, entry_index, price, raw, shares, charges, _money(abs(price - raw) * shares))


def _sell(position: _Position, bar: Bar, raw_price: Decimal, reason: str, assumptions: Assumptions) -> SimulatedTrade:
    slipped = raw_price * (Decimal(1) - assumptions.slippage_bps / BPS)
    price = _price(slipped if slipped > 0 else raw_price)
    notional = price * position.shares
    charges = _money(notional * assumptions.brokerage_percent / Decimal(100))
    if charges > notional:
        charges = _money(notional)
    entry_notional = position.entry_price * position.shares
    pnl = _money(notional - charges - entry_notional - position.entry_charges)
    ret = None
    cost_basis = entry_notional + position.entry_charges
    if cost_basis > 0:
        ret = ((notional - charges - cost_basis) / cost_basis * Decimal(100)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    slippage = _money(position.entry_slippage + abs(price - _price(raw_price)) * position.shares)
    return SimulatedTrade(
        position.signal_at,
        position.entry_at,
        bar.timestamp,
        position.entry_price,
        price,
        position.shares,
        position.entry_charges,
        charges,
        slippage,
        reason,
        pnl,
        ret,
    )


def _risk_exit(bar: Bar, position: _Position, assumptions: Assumptions) -> tuple[Decimal, str] | None:
    stop = None
    target = None
    if assumptions.stop_loss_percent is not None:
        stop = position.entry_price * (Decimal(1) - assumptions.stop_loss_percent / Decimal(100))
    if assumptions.take_profit_percent is not None:
        target = position.entry_price * (Decimal(1) + assumptions.take_profit_percent / Decimal(100))
    stop_hit = stop is not None and bar.low <= stop
    target_hit = target is not None and bar.high >= target
    if stop_hit and target_hit and stop is not None:
        return min(bar.open, stop), "ambiguous_stop_and_target"
    if stop_hit and stop is not None:
        return min(bar.open, stop), "stop_loss"
    if target_hit and target is not None:
        return bar.open if bar.open > target else target, "take_profit"
    return None


def _after_sale(cash: Decimal, trade: SimulatedTrade) -> Decimal:
    proceeds = trade.exit_price * trade.shares - trade.exit_charges
    return _money(cash + proceeds)


def _signal_time(bars: list[Bar], entry_index: int) -> datetime:
    if entry_index == 0:
        return bars[0].timestamp
    return bars[entry_index - 1].timestamp


def _standing_warnings(assumptions: Assumptions) -> list[str]:
    basis = "Gross of brokerage and slippage." if assumptions.result_basis == "gross" else "Net of the configured brokerage and slippage."
    return [
        "This is a historical simulation of one currently listed stock. It does not include delisted securities and it is not a forecast.",
        "Prices are raw daily closes and opens. Adjusted closes are not applied, so splits, dividends, and other corporate actions can change the result.",
        "No benchmark is shown because no historical index series is stored.",
        "A simulated stop is not a guarantee. Gaps and slippage can fill beyond the stop price.",
        basis,
        "Signals use only completed sessions. The fill is the next stored session open, except a final open position, which is closed at the last completed close.",
    ]


def _gap_warnings(bars: list[Bar], start: date, end: date) -> list[str]:
    dates = [session_date(bar.timestamp) for bar in bars if start <= session_date(bar.timestamp) <= end]
    if any((right - left).days > 10 for left, right in zip(dates, dates[1:], strict=False)):
        return ["A gap longer than 10 calendar days was left empty. No candle was invented."]
    return []


def _empty(status: str, assumptions: Assumptions, warnings: list[str]) -> Simulation:
    summary = summarize(assumptions.initial_capital, [], [], 0, result_basis=assumptions.result_basis)
    return Simulation(status, (), (), summary, tuple(dict.fromkeys(warnings)), ENGINE_VERSION, EXECUTION_CONVENTION, PRICE_BASIS, SIZING_VERSION)


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def _price(value: Decimal) -> Decimal:
    return value.quantize(PRICE, rounding=ROUND_HALF_UP)
