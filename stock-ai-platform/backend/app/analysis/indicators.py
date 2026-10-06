"""Deterministic indicator math. Inputs are closes and volumes, never estimated bars."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.analysis.bars import Bar
from app.analysis.config import ANNUALIZATION, PERFORMANCE_SESSIONS, VOLATILITY_OBSERVATIONS, WEEK52_SESSIONS

PLACES = Decimal("0.000001")


def _q(value: Decimal) -> Decimal:
    return value.quantize(PLACES)


def percent_distance(close: Decimal | None, bound: Decimal | None) -> Decimal | None:
    """Percent distance from a bound. A missing or zero bound is undefined."""
    if close is None or bound in (None, 0):
        return None
    return _q((close - bound) / bound * Decimal(100))


def sma(values: list[Decimal], period: int) -> list[Decimal | None]:
    result: list[Decimal | None] = [None] * len(values)
    if period < 1:
        return result
    window = Decimal(0)
    for index, value in enumerate(values):
        window += value
        if index >= period:
            window -= values[index - period]
        if index >= period - 1:
            result[index] = _q(window / Decimal(period))
    return result


def ema(values: list[Decimal], period: int) -> list[Decimal | None]:
    result: list[Decimal | None] = [None] * len(values)
    if period < 1 or len(values) < period:
        return result
    seed = sum(values[:period], Decimal(0)) / Decimal(period)
    result[period - 1] = _q(seed)
    weight = Decimal(2) / Decimal(period + 1)
    previous = seed
    for index in range(period, len(values)):
        previous = values[index] * weight + previous * (Decimal(1) - weight)
        result[index] = _q(previous)
    return result


def rsi(closes: list[Decimal], period: int = 14) -> list[Decimal | None]:
    result: list[Decimal | None] = [None] * len(closes)
    if period < 1 or len(closes) <= period:
        return result
    gains: list[Decimal] = []
    losses: list[Decimal] = []
    for index in range(1, len(closes)):
        change = closes[index] - closes[index - 1]
        gains.append(change if change > 0 else Decimal(0))
        losses.append(-change if change < 0 else Decimal(0))
    average_gain = sum(gains[:period], Decimal(0)) / Decimal(period)
    average_loss = sum(losses[:period], Decimal(0)) / Decimal(period)
    result[period] = _rsi_value(average_gain, average_loss)
    for index in range(period, len(gains)):
        average_gain = (average_gain * Decimal(period - 1) + gains[index]) / Decimal(period)
        average_loss = (average_loss * Decimal(period - 1) + losses[index]) / Decimal(period)
        result[index + 1] = _rsi_value(average_gain, average_loss)
    return result


def _rsi_value(average_gain: Decimal, average_loss: Decimal) -> Decimal | None:
    if average_gain == 0 and average_loss == 0:
        return None
    if average_loss == 0:
        return Decimal("100.000000")
    relative = average_gain / average_loss
    return _q(Decimal(100) - (Decimal(100) / (Decimal(1) + relative)))


def macd(
    closes: list[Decimal],
    fast: int = 12,
    slow: int = 26,
    signal_period: int = 9,
) -> tuple[list[Decimal | None], list[Decimal | None], list[Decimal | None]]:
    fast_line = ema(closes, fast)
    slow_line = ema(closes, slow)
    macd_line: list[Decimal | None] = [None] * len(closes)
    usable: list[Decimal] = []
    usable_at: list[int] = []
    for index, (fast_value, slow_value) in enumerate(zip(fast_line, slow_line, strict=True)):
        if fast_value is None or slow_value is None:
            continue
        value = _q(fast_value - slow_value)
        macd_line[index] = value
        usable.append(value)
        usable_at.append(index)
    signal_values = ema(usable, signal_period)
    signal: list[Decimal | None] = [None] * len(closes)
    histogram: list[Decimal | None] = [None] * len(closes)
    for offset, index in enumerate(usable_at):
        signal_value = signal_values[offset]
        if signal_value is None or macd_line[index] is None:
            continue
        signal[index] = signal_value
        histogram[index] = _q(macd_line[index] - signal_value)
    return macd_line, signal, histogram


def average_true_range(bars: list[Bar], period: int) -> list[Decimal | None]:
    result: list[Decimal | None] = [None] * len(bars)
    if period < 1 or len(bars) <= period:
        return result
    true_ranges: list[Decimal] = []
    for index, bar in enumerate(bars):
        if index == 0:
            true_ranges.append(bar.high - bar.low)
            continue
        previous_close = bars[index - 1].close
        true_ranges.append(
            max(bar.high - bar.low, abs(bar.high - previous_close), abs(bar.low - previous_close))
        )
    window = sum(true_ranges[1 : period + 1], Decimal(0))
    result[period] = _q(window / Decimal(period))
    for index in range(period + 1, len(bars)):
        window += true_ranges[index] - true_ranges[index - period]
        result[index] = _q(window / Decimal(period))
    return result


def log_return_volatility(closes: list[Decimal], interval: str) -> Decimal | None:
    if len(closes) <= VOLATILITY_OBSERVATIONS:
        return None
    if any(close <= 0 for close in closes[-(VOLATILITY_OBSERVATIONS + 1) :]):
        return None
    factor = ANNUALIZATION.get(interval)
    if factor is None:
        return None
    returns: list[Decimal] = []
    window = closes[-(VOLATILITY_OBSERVATIONS + 1) :]
    for previous, current in zip(window, window[1:], strict=False):
        ratio = current / previous
        returns.append(ratio.ln())
    mean = sum(returns, Decimal(0)) / Decimal(len(returns))
    variance = sum((item - mean) ** 2 for item in returns) / Decimal(len(returns) - 1)
    annualized = variance.sqrt() * Decimal(factor).sqrt() * Decimal(100)
    return _q(annualized)


def session_performance(closes: list[Decimal]) -> dict[str, Decimal | None]:
    latest = closes[-1] if closes else None
    results: dict[str, Decimal | None] = {}
    for label, sessions in PERFORMANCE_SESSIONS.items():
        if latest is None or latest == 0 or len(closes) <= sessions:
            results[label] = None
            continue
        prior = closes[-1 - sessions]
        if prior == 0:
            results[label] = None
            continue
        results[label] = _q((latest - prior) / prior * Decimal(100))
    return results


def week_range(bars: list[Bar]) -> tuple[Decimal | None, Decimal | None]:
    if len(bars) < WEEK52_SESSIONS:
        return None, None
    window = bars[-WEEK52_SESSIONS:]
    return max(bar.high for bar in window), min(bar.low for bar in window)


@dataclass(frozen=True)
class IndicatorSnapshot:
    rsi_14: Decimal | None
    macd: Decimal | None
    macd_signal: Decimal | None
    macd_histogram: Decimal | None
    sma_20: Decimal | None
    sma_50: Decimal | None
    sma_100: Decimal | None
    sma_200: Decimal | None
    ema_20: Decimal | None
    ema_50: Decimal | None
    volatility: Decimal | None
    average_volume: Decimal | None
    volume: int | None
    week52_high: Decimal | None
    week52_low: Decimal | None
    distance_from_high_percent: Decimal | None
    distance_from_low_percent: Decimal | None
    performance: dict[str, Decimal | None]
    sma_20_series: tuple[Decimal | None, ...]
    sma_50_series: tuple[Decimal | None, ...]


def indicator_snapshot(bars: list[Bar], interval: str) -> IndicatorSnapshot:
    closes = [bar.close for bar in bars]
    volumes = [Decimal(bar.volume) for bar in bars]
    rsi_values = rsi(closes)
    macd_line, signal, histogram = macd(closes)
    sma_20 = sma(closes, 20)
    sma_50 = sma(closes, 50)
    sma_100 = sma(closes, 100)
    sma_200 = sma(closes, 200)
    ema_20 = ema(closes, 20)
    ema_50 = ema(closes, 50)
    average_volumes = sma(volumes, 20)
    high, low = week_range(bars)
    last_close = closes[-1] if closes else None
    distance_high = None
    distance_low = None
    distance_high = percent_distance(last_close, high)
    distance_low = percent_distance(last_close, low)
    return IndicatorSnapshot(
        rsi_14=_last(rsi_values),
        macd=_last(macd_line),
        macd_signal=_last(signal),
        macd_histogram=_last(histogram),
        sma_20=_last(sma_20),
        sma_50=_last(sma_50),
        sma_100=_last(sma_100),
        sma_200=_last(sma_200),
        ema_20=_last(ema_20),
        ema_50=_last(ema_50),
        volatility=log_return_volatility(closes, interval),
        average_volume=_last(average_volumes),
        volume=bars[-1].volume if bars else None,
        week52_high=high,
        week52_low=low,
        distance_from_high_percent=distance_high,
        distance_from_low_percent=distance_low,
        performance=session_performance(closes),
        sma_20_series=tuple(sma_20),
        sma_50_series=tuple(sma_50),
    )


def _last(values: list[Decimal | None]) -> Decimal | None:
    return values[-1] if values else None
