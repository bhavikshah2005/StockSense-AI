from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.analysis.bars import Bar
from app.analysis.config import AnalysisConfig
from app.analysis.engine import analyze
from app.analysis.indicators import ema, rsi, session_performance, sma
from app.analysis.pivots import detect_pivots
from app.analysis.summary import build_conclusion
from app.analysis.support import find_zones
from app.analysis.indicators import IndicatorSnapshot

IST = ZoneInfo("Asia/Kolkata")
TIGHT = AnalysisConfig(pivot_left=2, pivot_right=2, min_pivot_gap=4)


def _bars(turns: list[tuple[int, float]], extra: int = 6, tail: float | None = None, volume: int = 1000) -> list[Bar]:
    last_index = turns[-1][0]
    length = last_index + extra + 1
    values = [turns[0][1]] * length
    for (start, start_price), (end, end_price) in zip(turns, turns[1:], strict=False):
        span = end - start
        for index in range(start, end + 1):
            weight = 0 if span == 0 else (index - start) / span
            values[index] = start_price + (end_price - start_price) * weight
    fill = turns[-1][1] if tail is None else tail
    for index in range(last_index, length):
        values[index] = fill
    stamp = datetime(2024, 1, 2, 9, 15, tzinfo=IST)
    bars: list[Bar] = []
    for price in values:
        decimal = Decimal(str(round(price, 4)))
        bars.append(Bar(stamp, decimal, decimal, decimal, decimal, volume))
        stamp += timedelta(days=1)
        while stamp.weekday() >= 5:
            stamp += timedelta(days=1)
    return bars


def _types(result: object) -> set[str]:
    return {pattern.pattern_type for pattern in result.patterns}  # type: ignore[attr-defined]


def _one(result: object, name: str):
    matches = [pattern for pattern in result.patterns if pattern.pattern_type == name]  # type: ignore[attr-defined]
    assert len(matches) == 1
    return matches[0]


def test_sma_ema_and_rsi_follow_the_documented_windows() -> None:
    values = [Decimal(index) for index in range(1, 8)]
    averages = sma(values, 3)
    assert averages[1] is None
    assert averages[2] == Decimal("2.000000")
    assert averages[5] == Decimal("5.000000")
    seeded = ema(values, 3)
    assert seeded[2] == Decimal("2.000000")
    flat = [Decimal(10)] * 20
    assert rsi(flat, 14)[-1] is None
    rising = [Decimal(index) for index in range(1, 30)]
    assert rsi(rising, 14)[-1] == Decimal("100.000000")


def test_performance_uses_session_offsets_not_calendar_days() -> None:
    closes = [Decimal(100), Decimal(100), Decimal(110)]
    performance = session_performance(closes)
    assert performance["1d"] == Decimal("10.000000")
    assert performance["1w"] is None


def test_pivot_is_unavailable_until_later_bars_confirm_it() -> None:
    bars = _bars([(0, 10), (6, 20), (12, 10)], extra=4)
    early = detect_pivots(bars[:8], left=2, right=2)
    assert all(pivot.index != 6 for pivot in early)
    confirmed = detect_pivots(bars, left=2, right=2)
    peak = next(pivot for pivot in confirmed if pivot.index == 6)
    assert peak.confirmed_at == bars[8].timestamp
    assert peak.confirmed_at > peak.timestamp


def test_flat_series_has_no_pivots_or_patterns() -> None:
    bars = [Bar(datetime(2024, 1, 2, 9, 15, tzinfo=IST) + timedelta(days=index), Decimal(50), Decimal(50), Decimal(50), Decimal(50), 10) for index in range(12)]
    result = analyze(bars, "1d", TIGHT)
    assert result.pivots == ()
    assert result.patterns == ()
    assert result.conclusion.category == "insufficient_data"


def test_double_top_develops_confirms_and_rejects_a_mismatch() -> None:
    shape = [(0, 90), (10, 110), (20, 85), (30, 109), (40, 100)]
    developing = analyze(_bars(shape, extra=4, tail=100), "1d", TIGHT)
    assert _one(developing, "double_top").status == "developing"
    confirmed = analyze(_bars(shape, extra=1, tail=70), "1d", TIGHT)
    assert _one(confirmed, "double_top").status == "confirmed"
    completed = analyze(_bars(shape, extra=6, tail=70), "1d", TIGHT)
    assert _one(completed, "double_top").status == "completed"
    invalidated = analyze(_bars(shape, extra=4, tail=120), "1d", TIGHT)
    assert _one(invalidated, "double_top").status == "invalidated"
    mismatch = analyze(_bars([(0, 90), (10, 110), (20, 85), (30, 150), (40, 100)], extra=4), "1d", TIGHT)
    assert "double_top" not in _types(mismatch)


def test_double_bottom_and_head_shoulders() -> None:
    bottom = analyze(_bars([(0, 120), (10, 90), (20, 115), (30, 91), (40, 110)], extra=4, tail=110), "1d", TIGHT)
    assert _one(bottom, "double_bottom").status == "developing"
    broken = analyze(_bars([(0, 120), (10, 90), (20, 115), (30, 91), (40, 110)], extra=2, tail=120), "1d", TIGHT)
    assert _one(broken, "double_bottom").status in {"confirmed", "completed"}
    shoulders = [(0, 90), (8, 100), (16, 84), (26, 120), (36, 86), (46, 101), (54, 96)]
    forming = analyze(_bars(shoulders, extra=4, tail=96), "1d", TIGHT)
    assert _one(forming, "head_and_shoulders").status == "developing"
    triggered = analyze(_bars(shoulders, extra=2, tail=70), "1d", TIGHT)
    assert _one(triggered, "head_and_shoulders").status in {"confirmed", "completed"}
    uneven = [(0, 90), (8, 100), (16, 84), (26, 120), (36, 86), (46, 140), (54, 96)]
    assert "head_and_shoulders" not in _types(analyze(_bars(uneven, extra=4), "1d", TIGHT))


def test_inverse_head_shoulders_and_triple_top() -> None:
    inverse = [(0, 110), (8, 100), (16, 116), (26, 80), (36, 114), (46, 101), (54, 108)]
    result = analyze(_bars(inverse, extra=4, tail=108), "1d", TIGHT)
    assert _one(result, "inverse_head_and_shoulders").status == "developing"
    triple = [(0, 90), (8, 100), (16, 90), (24, 101), (32, 89), (40, 100), (48, 95)]
    forming = analyze(_bars(triple, extra=4, tail=95), "1d", TIGHT)
    assert _one(forming, "triple_top").status == "developing"
    assert "triple_top" not in _types(analyze(_bars([(0, 90), (8, 100), (16, 90), (24, 130)], extra=4), "1d", TIGHT))


def test_triangle_flag_and_weak_pole() -> None:
    triangle = [(0, 80), (8, 100), (16, 86), (24, 101), (32, 92), (40, 100), (48, 96)]
    ranged = analyze(_bars(triangle, extra=4, tail=96), "1d", TIGHT)
    assert _one(ranged, "ascending_triangle").status == "developing"
    flag = analyze(
        _bars([(0, 110), (6, 100), (20, 145), (26, 132), (32, 138), (38, 128), (44, 134)], extra=4, tail=134),
        "1d",
        TIGHT,
    )
    assert _one(flag, "bull_flag").status == "developing"
    weak = analyze(_bars([(0, 100), (14, 104), (20, 102), (26, 103)], extra=4), "1d", TIGHT)
    assert "bull_flag" not in _types(weak)


def test_remaining_pattern_families_match_clear_shapes() -> None:
    rectangle = analyze(_bars([(0, 90), (8, 110), (16, 90), (24, 110), (32, 91), (40, 109), (48, 90)], extra=3, tail=90), "1d", TIGHT)
    assert "rectangle" in _types(rectangle)
    descending = analyze(_bars([(0, 90), (8, 120), (16, 91), (24, 112), (32, 90), (40, 104), (48, 91)], extra=3, tail=91), "1d", TIGHT)
    assert "descending_triangle" in _types(descending)
    symmetrical = analyze(_bars([(0, 80), (8, 120), (16, 90), (24, 112), (32, 98), (40, 106), (48, 101)], extra=3, tail=101), "1d", TIGHT)
    assert "symmetrical_triangle" in _types(symmetrical)
    rising = analyze(_bars([(0, 80), (8, 100), (16, 92), (24, 110), (32, 104), (40, 118), (48, 112)], extra=3, tail=112), "1d", TIGHT)
    assert "rising_wedge" in _types(rising)
    falling = analyze(_bars([(0, 120), (8, 100), (16, 112), (24, 90), (32, 100), (40, 82), (48, 90)], extra=3, tail=90), "1d", TIGHT)
    assert "falling_wedge" in _types(falling)
    bear = analyze(_bars([(0, 90), (6, 150), (20, 105), (26, 118), (32, 108), (38, 116), (44, 110)], extra=3, tail=110), "1d", TIGHT)
    assert "bear_flag" in _types(bear)
    triple_bottom = analyze(_bars([(0, 110), (8, 90), (16, 108), (24, 91), (32, 109), (40, 90), (48, 100)], extra=3, tail=100), "1d", TIGHT)
    assert "triple_bottom" in _types(triple_bottom)


def test_support_zone_counts_repeated_reactions_and_a_breach() -> None:
    bars = _bars([(0, 100), (8, 112), (16, 100), (24, 113), (32, 101), (40, 111)], extra=2, tail=111)
    zones = find_zones(bars, detect_pivots(bars, 2, 2), TIGHT)
    support = next(zone for zone in zones if zone.kind == "support")
    assert support.tests >= 2
    assert support.status == "active"
    breached = _bars([(0, 100), (8, 112), (16, 100), (24, 113), (32, 101), (40, 111)], extra=2, tail=80)
    broken = find_zones(breached, detect_pivots(breached, 2, 2), TIGHT)
    assert next(zone for zone in broken if zone.kind == "support").status == "breached"
    single = _bars([(0, 100), (8, 120), (16, 110)], extra=2)
    pivots = detect_pivots(single, 2, 2)
    assert find_zones(single, pivots, TIGHT, min_tests=2) == []
    assert len(find_zones(single, pivots, TIGHT, min_tests=1)) == 1


def test_summary_labels_conflict_and_does_not_instruct_a_trade() -> None:
    bars = _bars([(0, 100), (10, 110), (20, 105), (30, 120), (40, 115), (50, 130), (60, 125)], extra=8, tail=140)
    result = analyze(bars, "1d", TIGHT)
    text = result.conclusion.text.lower()
    for banned in ("buy", "sell", "hold", "guarantee", "invest"):
        assert banned not in text
    empty = IndicatorSnapshot(
        None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, {}, (), ()
    )
    short = build_conclusion(bars[:10], empty, [], [], [])
    assert short.category == "insufficient_data"
    assert "not a forecast" in short.text
