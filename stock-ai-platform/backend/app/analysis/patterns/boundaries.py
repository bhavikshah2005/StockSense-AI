"""Triangles, wedges, and rectangles from fitted pivot boundaries."""

from __future__ import annotations

from decimal import Decimal

from app.analysis.bars import Bar
from app.analysis.breakout import classify_cross
from app.analysis.config import AnalysisConfig
from app.analysis.patterns.common import PatternHit, fit_line, money, price_on_line, residual_ok
from app.analysis.pivots import Pivot


def detect_boundaries(bars: list[Bar], pivots: list[Pivot], config: AnalysisConfig) -> list[PatternHit]:
    if len(bars) < 12:
        return []
    highs = [pivot for pivot in pivots if pivot.kind == "high"]
    lows = [pivot for pivot in pivots if pivot.kind == "low"]
    if len(highs) < 2 or len(lows) < 2:
        return []
    highs = highs[-4:]
    lows = lows[-4:]
    start = min(highs[0].index, lows[0].index)
    end = max(highs[-1].index, lows[-1].index)
    if end - start < 12:
        return []
    upper_slope, upper_intercept = fit_line(highs)
    lower_slope, lower_intercept = fit_line(lows)
    if not residual_ok(highs, upper_slope, upper_intercept, config.boundary_residual):
        return []
    if not residual_ok(lows, lower_slope, lower_intercept, config.boundary_residual):
        return []
    reference = bars[end].close or Decimal(1)
    upper_rel = Decimal(str(upper_slope)) / abs(reference)
    lower_rel = Decimal(str(lower_slope)) / abs(reference)
    gap_start = price_on_line(upper_slope, upper_intercept, start) - price_on_line(lower_slope, lower_intercept, start)
    gap_end = price_on_line(upper_slope, upper_intercept, end) - price_on_line(lower_slope, lower_intercept, end)
    if gap_end <= 0 or gap_start <= 0:
        return []
    flat = config.flat_slope
    upper_flat = abs(upper_rel) < flat
    lower_flat = abs(lower_rel) < flat
    upper_up = upper_rel >= flat
    lower_up = lower_rel >= flat
    upper_down = upper_rel <= -flat
    lower_down = lower_rel <= -flat
    converging = gap_end < gap_start * Decimal("0.98")
    kind = _classify(
        upper_flat,
        lower_flat,
        upper_up,
        lower_up,
        upper_down,
        lower_down,
        converging,
        gap_start,
        gap_end,
        reference,
    )
    if kind is None:
        return []
    pattern_type, direction = kind

    def upper_at(index: int) -> Decimal:
        # Do not extend the fit past the last pivot. An open-ended line can invent a break.
        return price_on_line(upper_slope, upper_intercept, min(index, end))

    def lower_at(index: int) -> Decimal:
        return price_on_line(lower_slope, lower_intercept, min(index, end))

    last_close = bars[-1].close
    upper_now = upper_at(end)
    lower_now = lower_at(end)
    if last_close >= upper_now:
        status, confirmation = classify_cross(
            bars,
            end,
            upper_at,
            "above",
            lower_now,
            "below",
            config,
        )
        broken = "upper"
    elif last_close <= lower_now:
        status, confirmation = classify_cross(
            bars,
            end,
            lower_at,
            "below",
            upper_now,
            "above",
            config,
        )
        broken = "lower"
    else:
        status, confirmation, broken = "developing", None, "none"
    return [
        PatternHit(
            pattern_type=pattern_type,
            direction=direction,
            status=status,
            start_index=start,
            end_index=confirmation if confirmation is not None else end,
            pivots=tuple(highs + lows),
            levels={
                "upper": money(upper_now),
                "lower": money(lower_now),
                "boundary_crossed": broken,
            },
            boundaries={
                "upper": ((start, money(upper_at(start))), (end, money(upper_at(end)))),
                "lower": ((start, money(lower_at(start))), (end, money(lower_at(end)))),
            },
            confirmation_index=confirmation,
            invalidation_text=(
                "A developing formation is invalidated by a close through the opposite boundary before confirmation. "
                "After three closes beyond a boundary, a later close back through that boundary invalidates the cross."
            ),
            evidence=(
                f"{len(highs)} swing highs and {len(lows)} swing lows define the boundaries. "
                f"Upper slope per bar is {upper_rel:.4f} of price and lower slope per bar is {lower_rel:.4f}."
            ),
            limitations=("Boundary slope is a least-squares fit of the pivots, not a hand-drawn line.",),
        )
    ]


def _classify(
    upper_flat: bool,
    lower_flat: bool,
    upper_up: bool,
    lower_up: bool,
    upper_down: bool,
    lower_down: bool,
    converging: bool,
    gap_start: Decimal,
    gap_end: Decimal,
    reference: Decimal,
) -> tuple[str, str] | None:
    width = gap_end / abs(reference) if reference else Decimal(0)
    if upper_flat and lower_flat and Decimal("0.02") <= width <= Decimal("0.20"):
        if abs(gap_end - gap_start) / gap_start <= Decimal("0.15"):
            return "rectangle", "neutral"
        return None
    if not converging:
        return None
    if upper_flat and lower_up:
        return "ascending_triangle", "neutral"
    if lower_flat and upper_down:
        return "descending_triangle", "neutral"
    if upper_down and lower_up:
        return "symmetrical_triangle", "neutral"
    if upper_up and lower_up and lower_up:
        return "rising_wedge", "neutral"
    if upper_down and lower_down:
        return "falling_wedge", "neutral"
    return None
