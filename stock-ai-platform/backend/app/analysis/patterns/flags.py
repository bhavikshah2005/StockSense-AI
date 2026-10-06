"""Bull and bear flags: a measured pole followed by a smaller consolidation."""

from __future__ import annotations

from decimal import Decimal

from app.analysis.bars import Bar
from app.analysis.breakout import classify_cross
from app.analysis.config import AnalysisConfig
from app.analysis.patterns.common import PatternHit, money
from app.analysis.pivots import Pivot


def detect_flags(bars: list[Bar], pivots: list[Pivot], config: AnalysisConfig) -> list[PatternHit]:
    bull = _flag(bars, pivots, config, bullish=True)
    bear = _flag(bars, pivots, config, bullish=False)
    return [hit for hit in (bull, bear) if hit is not None]


def _flag(bars: list[Bar], pivots: list[Pivot], config: AnalysisConfig, *, bullish: bool) -> PatternHit | None:
    start_kind = "low" if bullish else "high"
    end_kind = "high" if bullish else "low"
    starts = [pivot for pivot in pivots if pivot.kind == start_kind]
    ends = [pivot for pivot in pivots if pivot.kind == end_kind]
    best: PatternHit | None = None
    for start in starts:
        for end in ends:
            if end.index < start.index + 3 or end.index - start.index > 40:
                continue
            if start.price == 0:
                continue
            pole = (end.price - start.price) / start.price if bullish else (start.price - end.price) / start.price
            if pole < config.flag_pole_min:
                continue
            window_start = end.index + 1
            if len(bars) - window_start < 4:
                continue
            window_end = min(len(bars) - 1, window_start + 19)
            for index in range(window_start, window_end + 1):
                close = bars[index].close
                broke = close > end.price if bullish else close < end.price
                if broke and index > window_start + 3:
                    window_end = index - 1
                    break
            window = bars[window_start : window_end + 1]
            if len(window) < 4:
                continue
            upper = max(bar.high for bar in window)
            lower = min(bar.low for bar in window)
            pole_height = abs(end.price - start.price)
            if pole_height == 0 or (upper - lower) > pole_height * config.flag_consolidation_ratio:
                continue
            if bullish and upper > end.price * Decimal("1.01") and bars[-1].close <= end.price:
                continue
            if not bullish and lower < end.price * Decimal("0.99") and bars[-1].close >= end.price:
                continue
            boundary = end.price
            side = "above" if bullish else "below"
            invalidation_side = "below" if bullish else "above"
            invalidation = lower if bullish else upper
            status, confirmation = classify_cross(
                bars,
                window_start,
                lambda _index, level=boundary: level,
                side,
                invalidation,
                invalidation_side,
                config,
            )
            hit = PatternHit(
                pattern_type="bull_flag" if bullish else "bear_flag",
                direction="bullish_structure" if bullish else "bearish_structure",
                status=status,
                start_index=start.index,
                end_index=confirmation if confirmation is not None else window_end,
                pivots=(start, end),
                levels={
                    "pole_start": money(start.price),
                    "pole_end": money(end.price),
                    "consolidation_upper": money(upper),
                    "consolidation_lower": money(lower),
                    "breakout": money(boundary),
                },
                boundaries={
                    "pole": ((start.index, money(start.price)), (end.index, money(end.price))),
                    "upper": ((window_start, money(upper)), (window_end, money(upper))),
                    "lower": ((window_start, money(lower)), (window_end, money(lower))),
                },
                confirmation_index=confirmation,
                invalidation_text=(
                    "A close through the far side of the consolidation before a breakout invalidates the flag. "
                    "The pole itself is a measured prior move, not a target."
                ),
                evidence=(
                    f"The prior move was {pole * 100:.1f}% over {end.index - start.index} bars. "
                    f"The following range is {upper - lower:.4f}, inside half of that move."
                ),
                limitations=("A flag does not imply that the prior move will repeat.",),
            )
            if best is None or hit.end_index >= best.end_index:
                best = hit
    return best
