"""Close-beyond-boundary confirmation.

A single close beyond the boundary confirms the cross. `completed` requires
that many later closes to remain beyond it. A return before that window does
not relabel the cross as failed. A return after the window is invalidated.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

from app.analysis.bars import Bar
from app.analysis.config import AnalysisConfig
from app.analysis.indicators import average_true_range


def price_buffer(bars: list[Bar], index: int, config: AnalysisConfig) -> Decimal:
    price = abs(bars[index].close)
    percent = price * config.breakout_buffer_pct
    ranges = average_true_range(bars, config.atr_period)
    atr = ranges[index] if index < len(ranges) else None
    if atr is None:
        return percent
    return max(percent, atr * config.atr_buffer_fraction)


def beyond(close: Decimal, boundary: Decimal, buffer: Decimal, side: str) -> bool:
    if side == "below":
        return close < boundary - buffer
    return close > boundary + buffer


def classify_cross(
    bars: list[Bar],
    start_index: int,
    boundary_at: Callable[[int], Decimal],
    side: str,
    invalidation: Decimal,
    invalidation_side: str,
    config: AnalysisConfig,
) -> tuple[str, int | None]:
    """Return status and the index of the confirming close, if one exists."""
    confirmation: int | None = None
    for index in range(start_index, len(bars)):
        close = bars[index].close
        buffer = price_buffer(bars, index, config)
        boundary = boundary_at(index)
        if confirmation is None and beyond(close, invalidation, Decimal(0), invalidation_side):
            return "invalidated", None
        if confirmation is None and beyond(close, boundary, buffer, side):
            confirmation = index
            break
    if confirmation is None:
        return "developing", None
    held = 0
    for index in range(confirmation, len(bars)):
        buffer = price_buffer(bars, index, config)
        boundary = boundary_at(index)
        if beyond(bars[index].close, boundary, buffer, side):
            held += 1
            continue
        if held >= config.completion_bars:
            return "invalidated", confirmation
        return "confirmed", confirmation
    if held >= config.completion_bars:
        return "completed", confirmation
    return "confirmed", confirmation


def volume_evidence(bars: list[Bar], index: int | None) -> str:
    if index is None or index < 20:
        return "unavailable"
    prior = [bars[offset].volume for offset in range(index - 20, index)]
    if any(volume < 0 for volume in prior) or bars[index].volume < 0:
        return "unavailable"
    if sum(prior) == 0:
        return "unavailable"
    average = sum(prior) / len(prior)
    if bars[index].volume > average:
        return "above_average"
    return "not_above_average"
