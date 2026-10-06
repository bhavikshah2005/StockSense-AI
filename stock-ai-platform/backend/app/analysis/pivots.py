"""Swing highs and lows.

A pivot at bar i is confirmed only after `right` later bars exist. Its
availability timestamp is that later bar, so a historical reading cannot use
the pivot before it could have been known.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.analysis.bars import Bar


@dataclass(frozen=True)
class Pivot:
    index: int
    timestamp: datetime
    confirmed_index: int
    confirmed_at: datetime
    kind: str
    price: Decimal


def detect_pivots(bars: list[Bar], left: int, right: int) -> list[Pivot]:
    if left < 1 or right < 1 or len(bars) < left + right + 1:
        return []
    pivots: list[Pivot] = []
    for index in range(left, len(bars) - right):
        high = bars[index].high
        low = bars[index].low
        highs = [bars[offset].high for offset in range(index - left, index + right + 1) if offset != index]
        lows = [bars[offset].low for offset in range(index - left, index + right + 1) if offset != index]
        confirmed_index = index + right
        confirmed_at = bars[confirmed_index].timestamp
        if all(high > other for other in highs):
            pivots.append(
                Pivot(index, bars[index].timestamp, confirmed_index, confirmed_at, "high", high)
            )
        if all(low < other for other in lows):
            pivots.append(
                Pivot(index, bars[index].timestamp, confirmed_index, confirmed_at, "low", low)
            )
    return pivots
