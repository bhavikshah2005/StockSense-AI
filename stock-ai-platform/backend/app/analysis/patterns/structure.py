"""Swing structure from the latest confirmed highs and lows."""

from __future__ import annotations

from app.analysis.patterns.common import PatternHit, money
from app.analysis.pivots import Pivot


def detect_structure(pivots: list[Pivot]) -> list[PatternHit]:
    highs = [pivot for pivot in pivots if pivot.kind == "high"]
    lows = [pivot for pivot in pivots if pivot.kind == "low"]
    if len(highs) < 2 or len(lows) < 2:
        return []
    previous_high, latest_high = highs[-2], highs[-1]
    previous_low, latest_low = lows[-2], lows[-1]
    higher = latest_high.price > previous_high.price and latest_low.price > previous_low.price
    lower = latest_high.price < previous_high.price and latest_low.price < previous_low.price
    if higher:
        kind = "higher_highs_higher_lows"
        direction = "bullish_structure"
        text = "The latest confirmed swing high and swing low are both above the prior pair."
    elif lower:
        kind = "lower_highs_lower_lows"
        direction = "bearish_structure"
        text = "The latest confirmed swing high and swing low are both below the prior pair."
    else:
        return []
    start = min(previous_high.index, previous_low.index)
    end = max(latest_high.index, latest_low.index)
    return [
        PatternHit(
            pattern_type=kind,
            direction=direction,
            status="developing",
            start_index=start,
            end_index=end,
            pivots=(previous_high, latest_high, previous_low, latest_low),
            levels={
                "prior_high": money(previous_high.price),
                "latest_high": money(latest_high.price),
                "prior_low": money(previous_low.price),
                "latest_low": money(latest_low.price),
            },
            boundaries={},
            confirmation_index=None,
            invalidation_text="A later confirmed swing that breaks this sequence changes the structure. This label is not a breakout.",
            evidence=text,
            limitations=("This describes confirmed swings only. It is not a price target.",),
        )
    ]
