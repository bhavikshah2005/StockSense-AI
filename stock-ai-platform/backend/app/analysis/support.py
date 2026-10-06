"""Support and resistance zones clustered from confirmed swing prices."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.analysis.bars import Bar
from app.analysis.config import AnalysisConfig
from app.analysis.patterns.common import money
from app.analysis.pivots import Pivot


@dataclass(frozen=True)
class Zone:
    kind: str
    lower: str
    upper: str
    tests: int
    last_test_index: int
    status: str
    pivot_indexes: tuple[int, ...]


def find_zones(bars: list[Bar], pivots: list[Pivot], config: AnalysisConfig, *, min_tests: int | None = None) -> list[Zone]:
    required = config.min_zone_tests if min_tests is None else min_tests
    if not bars:
        return []
    reference = bars[-1].close
    tolerance = abs(reference) * config.zone_tolerance
    zones: list[Zone] = []
    for kind, source in (("resistance", "high"), ("support", "low")):
        points = [pivot for pivot in pivots if pivot.kind == source]
        zones.extend(_cluster(points, kind, tolerance, bars[-1].close, required))
    return zones


def _cluster(points: list[Pivot], kind: str, tolerance: Decimal, last_close: Decimal, min_tests: int) -> list[Zone]:
    if not points:
        return []
    ordered = sorted(points, key=lambda pivot: pivot.price)
    groups: list[list[Pivot]] = [[ordered[0]]]
    for pivot in ordered[1:]:
        anchor = sum((item.price for item in groups[-1]), Decimal(0)) / Decimal(len(groups[-1]))
        if abs(pivot.price - anchor) <= tolerance:
            groups[-1].append(pivot)
        else:
            groups.append([pivot])
    zones: list[Zone] = []
    for group in groups:
        if len(group) < min_tests:
            continue
        lower = min(pivot.price for pivot in group)
        upper = max(pivot.price for pivot in group)
        if lower == upper:
            pad = tolerance / Decimal(2)
            lower -= pad
            upper += pad
        last = max(group, key=lambda pivot: pivot.index)
        if kind == "support":
            status = "active" if last_close >= lower else "breached"
        else:
            status = "active" if last_close <= upper else "breached"
        zones.append(
            Zone(
                kind,
                money(lower),
                money(upper),
                len(group),
                last.index,
                status,
                tuple(pivot.index for pivot in group),
            )
        )
    return zones
