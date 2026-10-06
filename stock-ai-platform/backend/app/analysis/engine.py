"""Run indicators, pivots, detectors, zones, and the summary on one bar slice."""

from __future__ import annotations

from dataclasses import dataclass

from app.analysis.bars import Bar, prepare_bars
from app.analysis.breakout import volume_evidence
from app.analysis.config import ANALYSIS_INTERVALS, MAX_ANALYSIS_BARS, WEEK52_SESSIONS, AnalysisConfig
from app.analysis.indicators import IndicatorSnapshot, indicator_snapshot
from app.analysis.patterns.boundaries import detect_boundaries
from app.analysis.patterns.common import PatternHit
from app.analysis.patterns.flags import detect_flags
from app.analysis.patterns.reversals import detect_reversals
from app.analysis.patterns.structure import detect_structure
from app.analysis.pivots import Pivot, detect_pivots
from app.analysis.summary import Conclusion, build_conclusion
from app.analysis.support import Zone, find_zones


@dataclass(frozen=True)
class BreakoutNote:
    source: str
    side: str
    status: str
    boundary: str
    confirmation_met: bool
    volume_evidence: str
    missing: tuple[str, ...]


@dataclass(frozen=True)
class Analysis:
    bars: tuple[Bar, ...]
    interval: str
    indicators: IndicatorSnapshot
    pivots: tuple[Pivot, ...]
    patterns: tuple[PatternHit, ...]
    zones: tuple[Zone, ...]
    breakouts: tuple[BreakoutNote, ...]
    conclusion: Conclusion
    limitations: tuple[str, ...]


def analyze(bars: list[Bar], interval: str, config: AnalysisConfig | None = None) -> Analysis:
    settings = config or AnalysisConfig()
    limitations: list[str] = []
    if interval not in ANALYSIS_INTERVALS:
        limitations.append("Pattern tolerances are calibrated for daily bars.")
    clean, notes = prepare_bars(bars)
    limitations.extend(notes)
    if len(clean) > MAX_ANALYSIS_BARS:
        clean = clean[-MAX_ANALYSIS_BARS:]
        limitations.append(f"Only the latest {MAX_ANALYSIS_BARS} bars were analyzed.")
    if len(clean) < WEEK52_SESSIONS:
        limitations.append("52-week high and low need 252 sessions.")
    if len(clean) < 200:
        limitations.append("The 200-session average needs 200 closes.")
    if len(clean) < settings.pivot_left + settings.pivot_right + 1:
        limitations.append("Not enough bars to confirm a swing pivot.")
    indicators = indicator_snapshot(clean, interval)
    pivots = tuple(detect_pivots(clean, settings.pivot_left, settings.pivot_right))
    patterns = (
        *detect_reversals(clean, list(pivots), settings),
        *detect_boundaries(clean, list(pivots), settings),
        *detect_flags(clean, list(pivots), settings),
        *detect_structure(list(pivots)),
    )
    zones = tuple(find_zones(clean, list(pivots), settings))
    breakouts = _breakouts(clean, patterns, zones)
    if not any(bar.volume > 0 for bar in clean):
        limitations.append("Volume is missing, so volume was not used as evidence.")
    conclusion = build_conclusion(clean, indicators, list(patterns), list(zones), limitations)
    return Analysis(tuple(clean), interval, indicators, pivots, tuple(patterns), zones, tuple(breakouts), conclusion, tuple(dict.fromkeys(limitations)))


def _breakouts(bars: list[Bar], patterns: list[PatternHit], zones: list[Zone]) -> list[BreakoutNote]:
    notes: list[BreakoutNote] = []
    for pattern in patterns:
        if pattern.pattern_type in {"higher_highs_higher_lows", "lower_highs_lower_lows"}:
            continue
        boundary = pattern.levels.get("neckline") or pattern.levels.get("breakout") or pattern.levels.get("upper")
        if boundary is None:
            continue
        side = "below" if pattern.direction == "bearish_structure" else "above"
        if pattern.direction == "neutral":
            crossed = pattern.levels.get("boundary_crossed", "none")
            side = "above" if crossed == "upper" else "below" if crossed == "lower" else "inside"
        met = pattern.confirmation_index is not None
        missing: list[str] = []
        volume = volume_evidence(bars, pattern.confirmation_index)
        if volume == "unavailable":
            missing.append("volume")
        if not met:
            missing.append("confirming_close")
        notes.append(
            BreakoutNote(
                source=pattern.pattern_type,
                side=side,
                status=pattern.status,
                boundary=boundary,
                confirmation_met=met,
                volume_evidence=volume,
                missing=tuple(missing),
            )
        )
    for zone in zones:
        if zone.status != "breached":
            continue
        notes.append(
            BreakoutNote(
                source=f"{zone.kind}_zone",
                side="below" if zone.kind == "support" else "above",
                status="confirmed",
                boundary=zone.lower if zone.kind == "support" else zone.upper,
                confirmation_met=True,
                volume_evidence=volume_evidence(bars, len(bars) - 1),
                missing=(),
            )
        )
    return notes
