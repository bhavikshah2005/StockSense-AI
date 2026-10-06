"""Head-and-shoulders and double/triple reversal rules."""

from __future__ import annotations

from decimal import Decimal

from app.analysis.bars import Bar
from app.analysis.breakout import classify_cross
from app.analysis.config import AnalysisConfig
from app.analysis.patterns.common import PatternHit, between, latest, line_value, money, relative_gap, retrace, spaced
from app.analysis.pivots import Pivot


def detect_reversals(bars: list[Bar], pivots: list[Pivot], config: AnalysisConfig) -> list[PatternHit]:
    hits: list[PatternHit] = []
    hits.extend(latest(_head_shoulders(bars, pivots, config, inverse=False)))
    hits.extend(latest(_head_shoulders(bars, pivots, config, inverse=True)))
    hits.extend(latest(_repeated(bars, pivots, config, kind="high", count=2)))
    hits.extend(latest(_repeated(bars, pivots, config, kind="low", count=2)))
    hits.extend(latest(_repeated(bars, pivots, config, kind="high", count=3)))
    hits.extend(latest(_repeated(bars, pivots, config, kind="low", count=3)))
    return hits


def _head_shoulders(
    bars: list[Bar],
    pivots: list[Pivot],
    config: AnalysisConfig,
    *,
    inverse: bool,
) -> list[PatternHit]:
    extreme_kind = "low" if inverse else "high"
    neck_kind = "high" if inverse else "low"
    extremes = [pivot for pivot in pivots if pivot.kind == extreme_kind]
    hits: list[PatternHit] = []
    for offset in range(len(extremes) - 2):
        left, head, right = extremes[offset : offset + 3]
        indexes = [left.index, head.index, right.index]
        if not spaced(indexes, config.min_pivot_gap):
            continue
        if inverse:
            if not (head.price < left.price and head.price < right.price):
                continue
        elif not (head.price > left.price and head.price > right.price):
            continue
        if relative_gap(left.price, right.price) > config.shoulder_tolerance:
            continue
        prominence = abs(head.price - left.price) / abs(head.price) if head.price else Decimal(0)
        if prominence < Decimal("0.01"):
            continue
        left_neck = between(pivots, left.index, head.index, neck_kind)
        right_neck = between(pivots, head.index, right.index, neck_kind)
        if not left_neck or not right_neck:
            continue
        neck_left = min(left_neck, key=lambda pivot: pivot.price) if not inverse else max(left_neck, key=lambda pivot: pivot.price)
        neck_right = min(right_neck, key=lambda pivot: pivot.price) if not inverse else max(right_neck, key=lambda pivot: pivot.price)
        side = "above" if inverse else "below"
        invalidation_side = "below" if inverse else "above"

        def boundary(index: int, start: Pivot = neck_left, end: Pivot = neck_right) -> Decimal:
            return line_value(start, end, index)

        status, confirmation = classify_cross(
            bars,
            right.index + 1,
            boundary,
            side,
            head.price,
            invalidation_side,
            config,
        )
        name = "inverse_head_and_shoulders" if inverse else "head_and_shoulders"
        direction = "bullish_structure" if inverse else "bearish_structure"
        neckline = boundary(right.index)
        hits.append(
            PatternHit(
                pattern_type=name,
                direction=direction,
                status=status,
                start_index=left.index,
                end_index=confirmation if confirmation is not None else right.index,
                pivots=(left, neck_left, head, neck_right, right),
                levels={
                    "left_shoulder": money(left.price),
                    "head": money(head.price),
                    "right_shoulder": money(right.price),
                    "neckline": money(neckline),
                },
                boundaries={"neckline": ((neck_left.index, money(neck_left.price)), (neck_right.index, money(neck_right.price)))},
                confirmation_index=confirmation,
                invalidation_text=(
                    "A close beyond the head before the neckline is crossed invalidates the structure. "
                    "After three closes beyond the neckline, a later close back through the neckline also invalidates it."
                ),
                evidence=(
                    f"Pivots at {money(left.price)}, {money(head.price)}, and {money(right.price)}. "
                    f"Shoulder difference is within the {config.shoulder_tolerance * 100:.0f}% tolerance. "
                    f"Neckline near {money(neckline)}."
                ),
                quality="clear" if relative_gap(left.price, right.price) <= config.shoulder_tolerance / 2 else "limited",
            )
        )
    return hits


def _repeated(
    bars: list[Bar],
    pivots: list[Pivot],
    config: AnalysisConfig,
    *,
    kind: str,
    count: int,
) -> list[PatternHit]:
    extremes = [pivot for pivot in pivots if pivot.kind == kind]
    other = "low" if kind == "high" else "high"
    names = {("high", 2): "double_top", ("low", 2): "double_bottom", ("high", 3): "triple_top", ("low", 3): "triple_bottom"}
    hits: list[PatternHit] = []
    for offset in range(len(extremes) - count + 1):
        group = extremes[offset : offset + count]
        indexes = [pivot.index for pivot in group]
        if not spaced(indexes, config.min_pivot_gap):
            continue
        prices = [pivot.price for pivot in group]
        if relative_gap(min(prices), max(prices)) > config.level_tolerance:
            continue
        pullbacks: list[Pivot] = []
        failed = False
        for left, right in zip(group, group[1:], strict=False):
            span = between(pivots, left.index, right.index, other)
            if not span:
                failed = True
                break
            chosen = min(span, key=lambda pivot: pivot.price) if kind == "high" else max(span, key=lambda pivot: pivot.price)
            reference = min(left.price, right.price) if kind == "high" else max(left.price, right.price)
            if retrace(reference, chosen.price) < config.min_retrace:
                failed = True
                break
            pullbacks.append(chosen)
        if failed or len(pullbacks) != count - 1:
            continue
        if kind == "high":
            neckline = min(pivot.price for pivot in pullbacks)
            side = "below"
            invalidation_side = "above"
            invalidation = max(prices)
            direction = "bearish_structure"
        else:
            neckline = max(pivot.price for pivot in pullbacks)
            side = "above"
            invalidation_side = "below"
            invalidation = min(prices)
            direction = "bullish_structure"
        status, confirmation = classify_cross(
            bars,
            group[-1].index + 1,
            lambda _index, level=neckline: level,
            side,
            invalidation,
            invalidation_side,
            config,
        )
        end_index = confirmation if confirmation is not None else group[-1].index
        hits.append(
            PatternHit(
                pattern_type=names[(kind, count)],
                direction=direction,
                status=status,
                start_index=group[0].index,
                end_index=end_index,
                pivots=tuple(group) + tuple(pullbacks),
                levels={
                    "peaks": ", ".join(money(price) for price in prices),
                    "neckline": money(neckline),
                    "invalidation": money(invalidation),
                },
                boundaries={"neckline": ((group[0].index, money(neckline)), (group[-1].index, money(neckline)))},
                confirmation_index=confirmation,
                invalidation_text=(
                    "Before confirmation, a close beyond the extreme of the repeated levels invalidates the structure. "
                    "After three closes beyond the neckline, a later close back through it also invalidates it."
                ),
                evidence=(
                    f"{count} {kind} pivots within {config.level_tolerance * 100}% "
                    f"and a retracement of at least {config.min_retrace * 100}% between them. "
                    f"Neckline at {money(neckline)}."
                ),
            )
        )
    return hits
