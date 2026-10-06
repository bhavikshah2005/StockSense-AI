"""Shared pattern result and price-structure helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from app.analysis.pivots import Pivot


@dataclass(frozen=True)
class PatternHit:
    pattern_type: str
    direction: str
    status: str
    start_index: int
    end_index: int
    pivots: tuple[Pivot, ...]
    levels: dict[str, str]
    boundaries: dict[str, tuple[tuple[int, str], ...]]
    confirmation_index: int | None
    invalidation_text: str
    evidence: str
    limitations: tuple[str, ...] = field(default_factory=tuple)
    quality: str = "clear"


def money(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.0001")), "f")


def relative_gap(left: Decimal, right: Decimal) -> Decimal:
    base = (abs(left) + abs(right)) / Decimal(2)
    if base == 0:
        return Decimal(0)
    return abs(left - right) / base


def between(pivots: list[Pivot], start: int, end: int, kind: str) -> list[Pivot]:
    return [pivot for pivot in pivots if pivot.kind == kind and start < pivot.index < end]


def spaced(indexes: list[int], minimum: int) -> bool:
    return all(right - left >= minimum for left, right in zip(indexes, indexes[1:], strict=False))


def retrace(extreme: Decimal, pullback: Decimal) -> Decimal:
    if extreme == 0:
        return Decimal(0)
    return abs(extreme - pullback) / abs(extreme)


def latest(hits: list[PatternHit]) -> list[PatternHit]:
    if not hits:
        return []
    return [max(hits, key=lambda hit: hit.end_index)]


def line_value(start: Pivot, end: Pivot, index: int) -> Decimal:
    span = Decimal(end.index - start.index)
    if span == 0:
        return start.price
    slope = (end.price - start.price) / span
    return start.price + slope * Decimal(index - start.index)


def fit_line(points: list[Pivot]) -> tuple[float, float]:
    count = len(points)
    xs = [float(point.index) for point in points]
    ys = [float(point.price) for point in points]
    mean_x = sum(xs) / count
    mean_y = sum(ys) / count
    variance = sum((item - mean_x) ** 2 for item in xs)
    if variance == 0:
        return 0.0, mean_y
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True)) / variance
    return slope, mean_y - slope * mean_x


def price_on_line(slope: float, intercept: float, index: int) -> Decimal:
    return Decimal(str(round(slope * index + intercept, 4)))


def residual_ok(points: list[Pivot], slope: float, intercept: float, tolerance: Decimal) -> bool:
    for point in points:
        fitted = price_on_line(slope, intercept, point.index)
        if point.price == 0:
            return False
        if abs(point.price - fitted) / abs(point.price) > tolerance:
            return False
    return True

