"""Performance figures from a finished simulation. Undefined ratios stay null."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from statistics import median

MONEY = Decimal("0.01")
RATIO = Decimal("0.000001")


@dataclass(frozen=True)
class EquityPoint:
    equity: Decimal
    shares: int


@dataclass(frozen=True)
class ClosedTrade:
    pnl: Decimal
    return_percent: Decimal | None
    entry_notional: Decimal
    exit_notional: Decimal
    charges: Decimal
    slippage_cost: Decimal


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def _ratio(value: Decimal) -> str:
    return format(value.quantize(RATIO, rounding=ROUND_HALF_UP), "f")


def summarize(
    initial: Decimal,
    points: list[EquityPoint],
    trades: list[ClosedTrade],
    sessions_in_market: int,
    *,
    result_basis: str,
) -> dict[str, object]:
    final = points[-1].equity if points else initial
    total_inr = _money(final - initial)
    total_percent = None
    if initial > 0:
        total_percent = _ratio((final - initial) / initial * Decimal(100))
    sessions = len(points)
    annualized = _annualized(initial, final, sessions)
    drawdown, duration = _drawdown(points)
    wins = [trade for trade in trades if trade.pnl > 0]
    losses = [trade for trade in trades if trade.pnl < 0]
    returns = [trade.return_percent for trade in trades if trade.return_percent is not None]
    gross_profit = sum((trade.pnl for trade in wins), Decimal(0))
    gross_loss = sum((trade.pnl for trade in losses), Decimal(0))
    profit_factor = None
    profit_factor_reason = None
    if not trades:
        profit_factor_reason = "No completed trades."
    elif gross_loss == 0:
        profit_factor_reason = "No losing trades, so profit factor is undefined."
    else:
        profit_factor = _ratio(gross_profit / abs(gross_loss))
    exposure = None
    if sessions:
        exposure = _ratio(Decimal(sessions_in_market) / Decimal(sessions) * Decimal(100))
    average_equity = sum((point.equity for point in points), Decimal(0)) / Decimal(sessions) if sessions else None
    traded = sum((trade.entry_notional + trade.exit_notional for trade in trades), Decimal(0))
    turnover = None
    turnover_reason = None
    if average_equity is None or average_equity <= 0:
        turnover_reason = "Average equity is not positive."
    else:
        turnover = _ratio(traded / average_equity)
    costs = _money(sum((trade.charges + trade.slippage_cost for trade in trades), Decimal(0)))
    return {
        "result_basis": result_basis,
        "initial_equity": format(_money(initial), "f"),
        "final_equity": format(_money(final), "f"),
        "total_return_inr": format(total_inr, "f"),
        "total_return_percent": total_percent,
        "annualized_return_percent": annualized,
        "annualized_return_reason": None if annualized else "Annualized return needs at least 252 sessions and positive ending equity. The exponent is 252 divided by the session count.",
        "max_drawdown_percent": drawdown,
        "max_drawdown_sessions": duration,
        "completed_trades": len(trades),
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "win_rate_percent": _ratio(Decimal(len(wins)) / Decimal(len(trades)) * Decimal(100)) if trades else None,
        "win_rate_reason": None if trades else "No completed trades.",
        "average_win_inr": format(_money(gross_profit / Decimal(len(wins))), "f") if wins else None,
        "average_loss_inr": format(_money(gross_loss / Decimal(len(losses))), "f") if losses else None,
        "average_trade_return_percent": _ratio(sum(returns, Decimal(0)) / Decimal(len(returns))) if returns else None,
        "median_trade_return_percent": _ratio(Decimal(str(median(returns)))) if returns else None,
        "profit_factor": profit_factor,
        "profit_factor_reason": profit_factor_reason,
        "exposure_percent": exposure,
        "turnover": turnover,
        "turnover_reason": turnover_reason,
        "transaction_costs_inr": format(costs, "f"),
        "sessions": sessions,
        "benchmark": {
            "available": False,
            "reason": "No historical index series is stored, so this run has no benchmark comparison.",
        },
    }


def _annualized(initial: Decimal, final: Decimal, sessions: int) -> str | None:
    if sessions < 252 or initial <= 0 or final <= 0:
        return None
    ratio = float(final / initial)
    exponent = 252 / sessions
    value = Decimal(str(ratio**exponent - 1)) * Decimal(100)
    return _ratio(value)


def _drawdown(points: list[EquityPoint]) -> tuple[str | None, int | None]:
    if not points or points[0].equity <= 0:
        return None, None
    peak = points[0].equity
    peak_index = 0
    worst = Decimal(0)
    longest = 0
    underwater_from: int | None = None
    for index, point in enumerate(points):
        if point.equity >= peak:
            if underwater_from is not None:
                longest = max(longest, index - underwater_from)
            peak = point.equity
            peak_index = index
            underwater_from = None
            continue
        if underwater_from is None:
            underwater_from = peak_index
        if peak > 0:
            worst = max(worst, (peak - point.equity) / peak)
    if underwater_from is not None:
        longest = max(longest, len(points) - 1 - underwater_from)
    return _ratio(worst * Decimal(100)), longest
