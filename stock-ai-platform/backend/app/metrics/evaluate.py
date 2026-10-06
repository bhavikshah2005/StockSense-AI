"""Condition checks. These functions do not load data and do not call a model."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

LEVEL_OPERATORS = frozenset({">", "<", ">=", "<=", "=", "between", "outside_range"})
CROSS_OPERATORS = frozenset({"crosses_above", "crosses_below"})


@dataclass(frozen=True)
class ResolvedThreshold:
    id: str
    metric_key: str
    scope: str
    operator: str
    basis: str
    threshold_value: Decimal | None
    threshold_high: Decimal | None
    definition_version: str
    effective_from: str | None
    description: str | None
    reason: str
    skipped: list[str]


@dataclass(frozen=True)
class MetricReading:
    value: Decimal | None
    previous: Decimal | None
    pair_current: tuple[Decimal | None, Decimal | None] | None
    pair_previous: tuple[Decimal | None, Decimal | None] | None
    reference: Decimal | None
    as_of: datetime | None
    source: str | None
    stale: bool
    invalid: bool


@dataclass(frozen=True)
class Evaluation:
    state: str
    explanation: str
    value: Decimal | None
    previous: Decimal | None
    reference: Decimal | None


def level_met(operator: str, value: Decimal, low: Decimal | None, high: Decimal | None) -> bool | None:
    if operator == ">" and low is not None:
        return value > low
    if operator == "<" and low is not None:
        return value < low
    if operator == ">=" and low is not None:
        return value >= low
    if operator == "<=" and low is not None:
        return value <= low
    if operator == "=" and low is not None:
        return value == low
    if operator == "between" and low is not None and high is not None:
        return low <= value <= high
    if operator == "outside_range" and low is not None and high is not None:
        return value < low or value > high
    return None


def cross_met(operator: str, previous: Decimal | None, current: Decimal | None, level: Decimal | None) -> bool | None:
    if previous is None or current is None or level is None:
        return None
    if operator == "crosses_above":
        return previous < level <= current
    if operator == "crosses_below":
        return previous > level >= current
    return None


def pair_cross_met(
    operator: str,
    previous: tuple[Decimal | None, Decimal | None] | None,
    current: tuple[Decimal | None, Decimal | None] | None,
) -> bool | None:
    if previous is None or current is None or previous[0] is None or previous[1] is None or current[0] is None or current[1] is None:
        return None
    before = previous[0] - previous[1]
    after = current[0] - current[1]
    if operator == "crosses_above":
        return before <= 0 < after
    if operator == "crosses_below":
        return before >= 0 > after
    return None


def evaluate_reading(metric_name: str, reading: MetricReading, threshold: ResolvedThreshold | None, *, event_kind: str | None) -> Evaluation:
    if threshold is None:
        return Evaluation("no_threshold_configured", f"No active threshold is configured for {metric_name}.", reading.value, reading.previous, reading.reference)
    if reading.invalid:
        return Evaluation("insufficient_data", f"The stored {metric_name} value cannot be used.", None, None, None)
    if reading.stale:
        shown = _num(reading.value)
        return Evaluation(
            "stale_data",
            f"The stored {metric_name} value{shown} is older than the freshness window, so it was not compared with the threshold.",
            reading.value,
            reading.previous,
            reading.reference,
        )
    if threshold.basis == "sector_benchmark":
        if reading.reference is None:
            return Evaluation(
                "context_unavailable",
                f"The {metric_name} threshold compares the stock with its sector, and that sector benchmark is not available.",
                reading.value,
                reading.previous,
                None,
            )
        if reading.value is None:
            return Evaluation("insufficient_data", f"No stored {metric_name} value is available.", None, None, reading.reference)
        met = level_met(threshold.operator, reading.value, reading.reference, None)
        if met is None:
            return Evaluation("insufficient_data", f"The {metric_name} condition cannot be checked.", reading.value, None, reading.reference)
        return _result(metric_name, met, reading.value, None, reading.reference, threshold, "the sector benchmark")
    if event_kind == "pair":
        met = pair_cross_met(threshold.operator, reading.pair_previous, reading.pair_current)
        if met is None:
            return Evaluation(
                "insufficient_data",
                f"A {metric_name} cross needs the previous and current readings. One stored reading is not enough.",
                reading.value,
                reading.previous,
                None,
            )
        return _result(metric_name, met, reading.value, reading.previous, None, threshold, "the previous stored reading")
    if event_kind == "level" and threshold.operator in CROSS_OPERATORS:
        met = cross_met(threshold.operator, reading.previous, reading.value, threshold.threshold_value)
        if met is None:
            return Evaluation(
                "insufficient_data",
                f"A {metric_name} crossing needs the previous reading and a threshold level. A single current value is not treated as a cross.",
                reading.value,
                reading.previous,
                None,
            )
        return _result(metric_name, met, reading.value, reading.previous, None, threshold, _bound(threshold))
    if reading.value is None:
        return Evaluation("insufficient_data", f"No stored {metric_name} value is available.", None, None, None)
    met = level_met(threshold.operator, reading.value, threshold.threshold_value, threshold.threshold_high)
    if met is None:
        return Evaluation("insufficient_data", f"The {metric_name} condition is incomplete.", reading.value, None, None)
    return _result(metric_name, met, reading.value, None, None, threshold, _bound(threshold))


def _result(
    metric_name: str,
    met: bool,
    value: Decimal | None,
    previous: Decimal | None,
    reference: Decimal | None,
    threshold: ResolvedThreshold,
    compared_with: str,
) -> Evaluation:
    state = "met" if met else "not_met"
    relation = "meets" if met else "does not meet"
    return Evaluation(
        state,
        (
            f"{metric_name} is {_num(value) or 'unavailable'} and {relation} the {threshold.scope} threshold "
            f"({threshold.operator} {compared_with}). {threshold.reason} This is not a trade instruction."
        ),
        value,
        previous,
        reference,
    )


def _bound(threshold: ResolvedThreshold) -> str:
    if threshold.operator in {"between", "outside_range"}:
        return f"{_num(threshold.threshold_value)} and {_num(threshold.threshold_high)}"
    return _num(threshold.threshold_value) or "the configured level"


def _num(value: Decimal | None) -> str:
    if value is None:
        return ""
    return format(value, "f")
