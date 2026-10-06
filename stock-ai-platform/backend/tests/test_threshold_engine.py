from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.metrics.evaluate import MetricReading, ResolvedThreshold, cross_met, evaluate_reading, level_met, pair_cross_met


def _threshold(operator: str, low: str | None = None, high: str | None = None, basis: str = "absolute") -> ResolvedThreshold:
    return ResolvedThreshold(
        id="1",
        metric_key="rsi_14",
        scope="platform",
        operator=operator,
        basis=basis,
        threshold_value=Decimal(low) if low is not None else None,
        threshold_high=Decimal(high) if high is not None else None,
        definition_version="thresholds-1",
        effective_from=None,
        description=None,
        reason="Selected the platform default.",
        skipped=[],
    )


def _reading(value: str | None, previous: str | None = None, reference: str | None = None, *, stale: bool = False) -> MetricReading:
    return MetricReading(
        Decimal(value) if value is not None else None,
        Decimal(previous) if previous is not None else None,
        None,
        None,
        Decimal(reference) if reference is not None else None,
        datetime(2026, 9, 24, tzinfo=UTC),
        "test",
        stale,
        False,
    )


def test_level_and_range_operators() -> None:
    assert level_met(">", Decimal("5"), Decimal("4"), None) is True
    assert level_met(">", Decimal("4"), Decimal("4"), None) is False
    assert level_met(">=", Decimal("4"), Decimal("4"), None) is True
    assert level_met("<", Decimal("3"), Decimal("4"), None) is True
    assert level_met("<=", Decimal("4"), Decimal("4"), None) is True
    assert level_met("=", Decimal("4"), Decimal("4"), None) is True
    assert level_met("between", Decimal("5"), Decimal("4"), Decimal("6")) is True
    assert level_met("between", Decimal("7"), Decimal("4"), Decimal("6")) is False
    assert level_met("outside_range", Decimal("7"), Decimal("4"), Decimal("6")) is True
    assert level_met("outside_range", Decimal("5"), Decimal("4"), Decimal("6")) is False


def test_cross_requires_previous_value() -> None:
    assert cross_met("crosses_above", Decimal("29"), Decimal("31"), Decimal("30")) is True
    assert cross_met("crosses_above", Decimal("31"), Decimal("32"), Decimal("30")) is False
    assert cross_met("crosses_below", Decimal("31"), Decimal("29"), Decimal("30")) is True
    assert cross_met("crosses_above", None, Decimal("31"), Decimal("30")) is None
    outcome = evaluate_reading("RSI 14", _reading("31"), _threshold("crosses_above", "30"), event_kind="level")
    assert outcome.state == "insufficient_data"


def test_pair_cross_uses_both_readings() -> None:
    assert pair_cross_met("crosses_above", (Decimal("9"), Decimal("10")), (Decimal("11"), Decimal("10"))) is True
    assert pair_cross_met("crosses_below", (Decimal("11"), Decimal("10")), (Decimal("9"), Decimal("10"))) is True
    assert pair_cross_met("crosses_above", None, (Decimal("11"), Decimal("10"))) is None


def test_missing_stale_and_context_states() -> None:
    assert evaluate_reading("P/E", _reading(None), None, event_kind=None).state == "no_threshold_configured"
    assert evaluate_reading("P/E", _reading(None), _threshold("<", "20"), event_kind=None).state == "insufficient_data"
    stale = evaluate_reading("P/E", _reading("18", stale=True), _threshold("<", "20"), event_kind=None)
    assert stale.state == "stale_data"
    assert "not compared" in stale.explanation
    missing_sector = evaluate_reading("P/E", _reading("18"), _threshold("<", basis="sector_benchmark"), event_kind=None)
    assert missing_sector.state == "context_unavailable"
    met = evaluate_reading("P/E", _reading("18", reference="22"), _threshold("<", basis="sector_benchmark"), event_kind=None)
    assert met.state == "met"
    assert "not a trade instruction" in met.explanation


def test_freshness_helper_marks_old_prices() -> None:
    from app.metrics.readings import _price_stale

    now = datetime(2026, 9, 24, 12, tzinfo=UTC)
    assert _price_stale(now - timedelta(days=8), now) is True
    assert _price_stale(now - timedelta(days=1), now) is False
