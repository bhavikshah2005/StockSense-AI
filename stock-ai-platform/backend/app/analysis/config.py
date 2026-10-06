"""Documented defaults for indicators, pivots, and pattern tolerances."""

from dataclasses import dataclass
from decimal import Decimal

INDICATOR_VERSION = "indicators-1"
DETECTOR_VERSION = "patterns-1"
PIVOT_VERSION = "pivots-1"

# Session offsets from the latest bar. These are trading observations, not calendar days.
PERFORMANCE_SESSIONS = {
    "1d": 1,
    "1w": 5,
    "1m": 21,
    "3m": 63,
    "6m": 126,
    "1y": 252,
}
WEEK52_SESSIONS = 252
VOLATILITY_OBSERVATIONS = 20
ANNUALIZATION = {
    "1d": 252,
    "1h": 252 * 6,
    "15m": 252 * 25,
    "5m": 252 * 75,
}
ANALYSIS_INTERVALS = frozenset({"1d"})
MAX_ANALYSIS_BARS = 400
MIN_DIRECTIONAL_BARS = 60


@dataclass(frozen=True)
class AnalysisConfig:
    pivot_left: int = 5
    pivot_right: int = 5
    level_tolerance: Decimal = Decimal("0.03")
    shoulder_tolerance: Decimal = Decimal("0.15")
    min_pivot_gap: int = 5
    min_retrace: Decimal = Decimal("0.03")
    breakout_buffer_pct: Decimal = Decimal("0.005")
    atr_period: int = 14
    atr_buffer_fraction: Decimal = Decimal("0.25")
    completion_bars: int = 3
    flag_pole_min: Decimal = Decimal("0.10")
    flag_consolidation_ratio: Decimal = Decimal("0.50")
    zone_tolerance: Decimal = Decimal("0.015")
    min_zone_tests: int = 2
    flat_slope: Decimal = Decimal("0.0015")
    boundary_residual: Decimal = Decimal("0.025")
