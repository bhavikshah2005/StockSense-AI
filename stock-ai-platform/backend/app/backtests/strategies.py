"""Fixed strategy registry. Users pass validated parameters, not code."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.analysis.bars import Bar
from app.analysis.indicators import macd, rsi, sma
from app.backtests.patterns import pattern_signals

StrategyError = ValueError


@dataclass(frozen=True)
class ParameterSpec:
    name: str
    label: str
    kind: str
    minimum: int
    maximum: int
    default: int
    description: str


@dataclass(frozen=True)
class StrategySpec:
    key: str
    version: str
    name: str
    description: str
    holds_overnight: bool
    direction: str
    required_data: str
    entry_rule: str
    exit_rule: str
    missing_data: str
    parameters: tuple[ParameterSpec, ...]


def _int_param(name: str, label: str, minimum: int, maximum: int, default: int, description: str) -> ParameterSpec:
    return ParameterSpec(name, label, "integer", minimum, maximum, default, description)


SMA = StrategySpec(
    key="sma_crossover",
    version="1",
    name="Moving-average crossover",
    description="Long-only test of a short simple moving average crossing a longer one. A cross is not a prediction.",
    holds_overnight=True,
    direction="long_only",
    required_data="Daily raw closes. The long average must already be defined before the test window.",
    entry_rule="After a completed session, enter when the short average moves from at or below the long average to above it.",
    exit_rule="Exit when the short average moves from above the long average to at or below it, or when a configured stop, target, or holding limit is reached.",
    missing_data="A session with an undefined average produces no signal. Missing sessions are not filled.",
    parameters=(
        _int_param("short_period", "Short period", 2, 100, 20, "Sessions in the shorter average. Must be less than the long period."),
        _int_param("long_period", "Long period", 5, 200, 50, "Sessions in the longer average."),
    ),
)

RSI = StrategySpec(
    key="rsi_cross",
    version="1",
    name="RSI cross",
    description="Long-only test of the 14-session RSI crossing configured levels. A cross is not a prediction.",
    holds_overnight=True,
    direction="long_only",
    required_data="Daily raw closes and the existing RSI function.",
    entry_rule="Enter when RSI finishes a session at or above the entry level after finishing the previous session below it.",
    exit_rule="Exit when RSI finishes a session at or below the exit level after finishing the previous session above it, or when a configured stop, target, or holding limit is reached.",
    missing_data="Undefined RSI produces no signal. Equal averages and flat RSI do not count as a cross.",
    parameters=(
        _int_param("period", "RSI period", 2, 50, 14, "Sessions used by RSI."),
        _int_param("entry_level", "Entry level", 1, 80, 30, "Enter on a cross up through this level."),
        _int_param("exit_level", "Exit level", 20, 99, 70, "Exit on a cross down through this level. Must be above the entry level."),
    ),
)

MACD = StrategySpec(
    key="macd_cross",
    version="1",
    name="MACD cross",
    description="Long-only test of the MACD line crossing its signal line. Periods are the existing 12, 26, and 9 defaults. A cross is not a prediction.",
    holds_overnight=True,
    direction="long_only",
    required_data="Daily raw closes and the existing MACD function.",
    entry_rule="Enter when the MACD line finishes a session above the signal line after finishing at or below it.",
    exit_rule="Exit when the MACD line finishes a session at or below the signal line after finishing above it, or when a configured stop, target, or holding limit is reached.",
    missing_data="Sessions before the signal line exists produce no signal.",
    parameters=(),
)

COMBO = StrategySpec(
    key="sma_rsi",
    version="1",
    name="SMA and RSI combination",
    description="Long-only test that requires both a short average above a long average and an RSI cross up. Neither condition is a prediction.",
    holds_overnight=True,
    direction="long_only",
    required_data="Daily raw closes, SMA, and RSI.",
    entry_rule="Enter when the short average is above the long average and RSI crosses up through the entry level on the same completed session.",
    exit_rule="Exit when the short average is at or below the long average, or RSI crosses down through the exit level. A configured stop, target, or holding limit can also exit.",
    missing_data="If either indicator is undefined, the session has no signal. If both entry and exit would be true, an open position exits and a flat book does not enter.",
    parameters=(
        _int_param("short_period", "Short period", 2, 100, 20, "Sessions in the shorter average."),
        _int_param("long_period", "Long period", 5, 200, 50, "Sessions in the longer average."),
        _int_param("period", "RSI period", 2, 50, 14, "Sessions used by RSI."),
        _int_param("entry_level", "Entry level", 1, 80, 30, "RSI cross-up level."),
        _int_param("exit_level", "Exit level", 20, 99, 70, "RSI cross-down level."),
    ),
)

PATTERN = StrategySpec(
    key="bullish_reversal",
    version="1",
    name="Bullish reversal confirmation",
    description="Long-only test of inverse head-and-shoulders, double-bottom, and triple-bottom confirmations from the existing detector. Confirmation is not a prediction.",
    holds_overnight=True,
    direction="long_only",
    required_data="Daily OHLC bars and the existing reversal detector. The signal time is the later of the confirming close and the last pivot confirmation.",
    entry_rule="Enter after a bullish reversal is confirmed on data available through that session. The formation's earlier pivots are not entry times.",
    exit_rule="This strategy has no opposite-pattern exit. A position exits on a configured stop, target, holding limit, or the final completed close.",
    missing_data="Developing or invalidated structures produce no entry. The detector's latest-structure rule is applied only to bars available at that session.",
    parameters=(),
)

REGISTRY: dict[str, StrategySpec] = {item.key: item for item in (SMA, RSI, MACD, COMBO, PATTERN)}


def list_strategies() -> list[StrategySpec]:
    return list(REGISTRY.values())


def get_strategy(key: str, version: str) -> StrategySpec:
    spec = REGISTRY.get(key)
    if spec is None or spec.version != version:
        raise StrategyError("unsupported_strategy")
    return spec


def validate_parameters(spec: StrategySpec, raw: dict[str, object]) -> dict[str, int]:
    unknown = set(raw) - {item.name for item in spec.parameters}
    if unknown:
        raise StrategyError("unknown_parameter")
    parsed: dict[str, int] = {}
    for item in spec.parameters:
        value = raw.get(item.name, item.default)
        if isinstance(value, bool) or not isinstance(value, int):
            raise StrategyError("invalid_parameter")
        if value < item.minimum or value > item.maximum:
            raise StrategyError("invalid_parameter")
        parsed[item.name] = value
    if "short_period" in parsed and "long_period" in parsed and parsed["short_period"] >= parsed["long_period"]:
        raise StrategyError("invalid_parameter")
    if "entry_level" in parsed and "exit_level" in parsed and parsed["entry_level"] >= parsed["exit_level"]:
        raise StrategyError("invalid_parameter")
    return parsed


def warmup_sessions(spec: StrategySpec, params: dict[str, int]) -> int:
    if spec.key == "sma_crossover":
        return params["long_period"]
    if spec.key == "rsi_cross":
        return params["period"] + 1
    if spec.key == "macd_cross":
        return 34
    if spec.key == "sma_rsi":
        return max(params["long_period"], params["period"] + 1)
    return 11


def build_signals(spec: StrategySpec, params: dict[str, int], bars: list[Bar]) -> dict[int, set[str]]:
    closes = [bar.close for bar in bars]
    if spec.key == "sma_crossover":
        events = _cross(sma(closes, params["short_period"]), sma(closes, params["long_period"]))
    elif spec.key == "rsi_cross":
        events = _threshold(rsi(closes, params["period"]), params["entry_level"], params["exit_level"])
    elif spec.key == "macd_cross":
        line, signal, _histogram = macd(closes)
        events = _cross(line, signal)
    elif spec.key == "sma_rsi":
        events = _combo(closes, params)
    elif spec.key == "bullish_reversal":
        events = pattern_signals(bars)
    else:
        raise StrategyError("unsupported_strategy")
    scheduled: dict[int, set[str]] = {}
    for index, action in events:
        scheduled.setdefault(index, set()).add(action)
    return scheduled


def _cross(fast: list[Decimal | None], slow: list[Decimal | None]) -> list[tuple[int, str]]:
    events: list[tuple[int, str]] = []
    for index in range(1, len(fast)):
        previous_fast, previous_slow = fast[index - 1], slow[index - 1]
        current_fast, current_slow = fast[index], slow[index]
        if None in (previous_fast, previous_slow, current_fast, current_slow):
            continue
        was_above = previous_fast > previous_slow
        is_above = current_fast > current_slow
        if not was_above and is_above:
            events.append((index, "enter"))
        elif was_above and not is_above:
            events.append((index, "exit"))
    return events


def _threshold(values: list[Decimal | None], entry: int, exit_level: int) -> list[tuple[int, str]]:
    events: list[tuple[int, str]] = []
    entry_level = Decimal(entry)
    exit_bound = Decimal(exit_level)
    for index in range(1, len(values)):
        previous, current = values[index - 1], values[index]
        if previous is None or current is None:
            continue
        if previous < entry_level <= current:
            events.append((index, "enter"))
        if previous > exit_bound >= current:
            events.append((index, "exit"))
    return events


def _combo(closes: list[Decimal], params: dict[str, int]) -> list[tuple[int, str]]:
    short_line = sma(closes, params["short_period"])
    long_line = sma(closes, params["long_period"])
    rsi_line = rsi(closes, params["period"])
    entry_level = Decimal(params["entry_level"])
    exit_bound = Decimal(params["exit_level"])
    events: list[tuple[int, str]] = []
    for index in range(1, len(closes)):
        if None in (short_line[index], long_line[index], rsi_line[index], rsi_line[index - 1]):
            continue
        short_above = short_line[index] > long_line[index]
        crossed_up = rsi_line[index - 1] < entry_level <= rsi_line[index]
        crossed_down = rsi_line[index - 1] > exit_bound >= rsi_line[index]
        if short_above and crossed_up:
            events.append((index, "enter"))
        if not short_above or crossed_down:
            if short_line[index - 1] is not None and long_line[index - 1] is not None:
                events.append((index, "exit"))
    return events
