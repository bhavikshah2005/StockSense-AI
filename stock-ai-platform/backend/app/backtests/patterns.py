"""Causal bullish-reversal signals.

The public detector keeps the latest structure in a window. This walker only
passes bars through the session being judged, then waits until both the
confirming close and every pivot confirmation are inside that window.
"""

from __future__ import annotations

from app.analysis.bars import Bar
from app.analysis.config import AnalysisConfig
from app.analysis.patterns.common import PatternHit
from app.analysis.patterns.reversals import detect_reversals
from app.analysis.pivots import detect_pivots


def signal_bar(hit: PatternHit) -> int | None:
    """Index when the confirmation could have been known. Earlier pivots are not enough."""
    if hit.direction != "bullish_structure" or hit.confirmation_index is None:
        return None
    if hit.status not in {"confirmed", "completed"}:
        return None
    ready = hit.confirmation_index
    if hit.pivots:
        ready = max(ready, max(pivot.confirmed_index for pivot in hit.pivots))
    return ready


def pattern_signals(bars: list[Bar]) -> list[tuple[int, str]]:
    config = AnalysisConfig()
    signals: list[tuple[int, str]] = []
    seen: set[tuple[str, int, int]] = set()
    for end in range(1, len(bars) + 1):
        prefix = bars[:end]
        hits = detect_reversals(prefix, detect_pivots(prefix, config.pivot_left, config.pivot_right), config)
        index = end - 1
        for hit in hits:
            ready = signal_bar(hit)
            if ready != index or hit.confirmation_index is None:
                continue
            key = (hit.pattern_type, hit.start_index, hit.confirmation_index)
            if key in seen or any(existing == index for existing, _action in signals):
                continue
            seen.add(key)
            signals.append((index, "enter"))
    return signals
