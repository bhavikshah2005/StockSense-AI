"""Turn indicator, pattern, and zone evidence into a fixed rubric conclusion."""

from __future__ import annotations

from dataclasses import dataclass

from app.analysis.bars import Bar
from app.analysis.config import MIN_DIRECTIONAL_BARS
from app.analysis.indicators import IndicatorSnapshot
from app.analysis.patterns.common import PatternHit
from app.analysis.support import Zone

BULLISH_PATTERNS = frozenset(
    {"inverse_head_and_shoulders", "double_bottom", "triple_bottom", "bull_flag", "higher_highs_higher_lows"}
)
BEARISH_PATTERNS = frozenset(
    {"head_and_shoulders", "double_top", "triple_top", "bear_flag", "lower_highs_lower_lows"}
)
CONFIRMED = frozenset({"confirmed", "completed"})


@dataclass(frozen=True)
class Conclusion:
    category: str
    text: str
    conflicts: tuple[str, ...]
    invalidation: tuple[str, ...]


def build_conclusion(
    bars: list[Bar],
    indicators: IndicatorSnapshot,
    patterns: list[PatternHit],
    zones: list[Zone],
    limitations: list[str],
) -> Conclusion:
    conflicts: list[str] = []
    invalidation = [pattern.invalidation_text for pattern in patterns if pattern.pattern_type not in {"higher_highs_higher_lows", "lower_highs_lower_lows"}]
    structure = next((pattern for pattern in patterns if pattern.pattern_type in {"higher_highs_higher_lows", "lower_highs_lower_lows"}), None)
    trend = _trend(structure, indicators, bars)
    momentum, momentum_conflicts = _momentum(indicators)
    conflicts.extend(momentum_conflicts)
    pattern_text = _patterns(patterns)
    zone_text = _zones(zones)
    volume_text = _volume(indicators)
    bullish = _bullish(structure, indicators, patterns, bars)
    bearish = _bearish(structure, indicators, patterns, bars)
    if bullish and bearish:
        conflicts.append("Trend or momentum evidence points in both directions.")
    if len(bars) < MIN_DIRECTIONAL_BARS:
        category = "insufficient_data"
    elif not bullish and not bearish:
        category = "no_clear_direction"
    elif bullish and bearish:
        category = "mixed_evidence"
    elif bullish:
        category = "bullish_evidence"
    else:
        category = "bearish_evidence"
    parts = [
        trend,
        momentum,
        pattern_text,
        zone_text,
        volume_text,
    ]
    if conflicts:
        parts.append("Conflicting evidence: " + " ".join(conflicts))
    if limitations:
        parts.append("Limitations: " + " ".join(dict.fromkeys(limitations)))
    parts.append("This is an interpretation of historical prices. It is not a forecast and it is not a trade instruction.")
    return Conclusion(category, " ".join(part for part in parts if part), tuple(dict.fromkeys(conflicts)), tuple(dict.fromkeys(invalidation)))


def _trend(structure: PatternHit | None, indicators: IndicatorSnapshot, bars: list[Bar]) -> str:
    if structure is None:
        swing = "Recent confirmed swings do not form a consistent higher-high or lower-low sequence."
    elif structure.pattern_type == "higher_highs_higher_lows":
        swing = "Recent confirmed swing highs and swing lows are rising."
    else:
        swing = "Recent confirmed swing highs and swing lows are falling."
    if not bars or indicators.sma_20 is None or indicators.sma_50 is None:
        return swing
    close = bars[-1].close
    if close > indicators.sma_20 and close > indicators.sma_50:
        return swing + " The latest close is above the 20-session and 50-session averages."
    if close < indicators.sma_20 and close < indicators.sma_50:
        return swing + " The latest close is below the 20-session and 50-session averages."
    return swing + " The latest close is between the 20-session and 50-session averages."


def _momentum(indicators: IndicatorSnapshot) -> tuple[str, list[str]]:
    conflicts: list[str] = []
    if indicators.rsi_14 is None and indicators.macd_histogram is None:
        return "RSI and MACD are unavailable for this window.", conflicts
    parts: list[str] = []
    rsi_bias = "neutral"
    macd_bias = "neutral"
    if indicators.rsi_14 is not None:
        if indicators.rsi_14 >= 60:
            rsi_bias = "bullish"
            parts.append(f"RSI 14 is {indicators.rsi_14}, at or above 60.")
        elif indicators.rsi_14 <= 40:
            rsi_bias = "bearish"
            parts.append(f"RSI 14 is {indicators.rsi_14}, at or below 40.")
        else:
            parts.append(f"RSI 14 is {indicators.rsi_14}, between 40 and 60.")
    if indicators.macd_histogram is not None:
        if indicators.macd_histogram > 0:
            macd_bias = "bullish"
            parts.append("The MACD histogram is above zero.")
        elif indicators.macd_histogram < 0:
            macd_bias = "bearish"
            parts.append("The MACD histogram is below zero.")
        else:
            parts.append("The MACD histogram is zero.")
    if rsi_bias != "neutral" and macd_bias != "neutral" and rsi_bias != macd_bias:
        conflicts.append("RSI and the MACD histogram point in different directions.")
    return " ".join(parts), conflicts


def _patterns(patterns: list[PatternHit]) -> str:
    named = [pattern for pattern in patterns if pattern.pattern_type not in {"higher_highs_higher_lows", "lower_highs_lower_lows"}]
    if not named:
        return "No reliable chart pattern met the detection rules."
    pieces = [f"{pattern.pattern_type.replace('_', ' ')} is {pattern.status}." for pattern in named]
    return "Detected formations: " + " ".join(pieces)


def _zones(zones: list[Zone]) -> str:
    useful = [zone for zone in zones if zone.tests >= 2]
    if not useful:
        return "No support or resistance zone has more than one observed swing reaction in this window."
    pieces = [
        f"{zone.kind} {zone.lower} to {zone.upper} has {zone.tests} observed reactions and is {zone.status}."
        for zone in useful
    ]
    return " ".join(pieces)


def _volume(indicators: IndicatorSnapshot) -> str:
    if indicators.volume is None or indicators.average_volume is None:
        return "Volume evidence is unavailable."
    if indicators.average_volume == 0:
        return "Volume evidence is unavailable because the 20-session average is zero."
    if indicators.volume > indicators.average_volume:
        return "The latest volume is above the 20-session average volume. That is context, not confirmation by itself."
    return "The latest volume is not above the 20-session average volume."


def _bullish(structure: PatternHit | None, indicators: IndicatorSnapshot, patterns: list[PatternHit], bars: list[Bar]) -> bool:
    if structure is not None and structure.pattern_type == "higher_highs_higher_lows":
        return True
    if bars and indicators.sma_20 is not None and indicators.sma_50 is not None:
        close = bars[-1].close
        if close > indicators.sma_20 and close > indicators.sma_50:
            return True
    if indicators.rsi_14 is not None and indicators.rsi_14 >= 60:
        return True
    if indicators.macd_histogram is not None and indicators.macd_histogram > 0:
        return True
    return any(pattern.pattern_type in BULLISH_PATTERNS and pattern.status in CONFIRMED for pattern in patterns)


def _bearish(structure: PatternHit | None, indicators: IndicatorSnapshot, patterns: list[PatternHit], bars: list[Bar]) -> bool:
    if structure is not None and structure.pattern_type == "lower_highs_lower_lows":
        return True
    if bars and indicators.sma_20 is not None and indicators.sma_50 is not None:
        close = bars[-1].close
        if close < indicators.sma_20 and close < indicators.sma_50:
            return True
    if indicators.rsi_14 is not None and indicators.rsi_14 <= 40:
        return True
    if indicators.macd_histogram is not None and indicators.macd_histogram < 0:
        return True
    return any(pattern.pattern_type in BEARISH_PATTERNS and pattern.status in CONFIRMED for pattern in patterns)
