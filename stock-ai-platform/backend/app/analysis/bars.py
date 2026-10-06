"""Price bars used by indicators and pattern detection.

The canonical price is `close`. `adjusted_close` is not required and is not
read here, because stored adjusted closes are often missing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class Bar:
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int

    def valid(self) -> bool:
        if self.timestamp.tzinfo is None:
            return False
        if self.volume < 0:
            return False
        prices = (self.open, self.high, self.low, self.close)
        if any(price < 0 for price in prices):
            return False
        return self.high >= self.low and self.high >= self.open and self.high >= self.close and self.low <= self.open and self.low <= self.close


def prepare_bars(bars: list[Bar]) -> tuple[list[Bar], list[str]]:
    """Drop invalid bars and duplicate timestamps. Do not invent missing sessions."""
    notes: list[str] = []
    ordered = sorted(bars, key=lambda bar: bar.timestamp)
    kept: list[Bar] = []
    for bar in ordered:
        if not bar.valid():
            notes.append("A bar with a missing timezone or inconsistent OHLC was excluded.")
            continue
        if kept and kept[-1].timestamp == bar.timestamp:
            kept[-1] = bar
            notes.append("A duplicate timestamp was collapsed to the last bar.")
            continue
        kept.append(bar)
    return kept, list(dict.fromkeys(notes))
