"""Alert kinds the stored data layer can evaluate. This is not a trading signal list."""

from app.analysis.summary import BEARISH_PATTERNS, BULLISH_PATTERNS
from app.metrics.registry import METRICS

PATTERN_TYPES = tuple(sorted(BULLISH_PATTERNS | BEARISH_PATTERNS))
PATTERN_STATUSES = ("confirmed", "invalidated", "completed")
PRICE_INTERVALS = ("1d", "5d", "20d")
PRICE_OPERATORS = (">", "<", ">=", "<=", "crosses_above", "crosses_below")
PERCENT_OPERATORS = (">", "<")
REPEAT_MODES = ("once", "repeat")
STATUSES = ("active", "paused", "triggered", "disabled")


def catalog_payload() -> dict[str, object]:
    fundamentals = [item for item in METRICS if item.category == "fundamental"]
    technical = [item for item in METRICS if item.category == "technical"]
    return {
        "price": {
            "metrics": [
                {
                    "key": "price",
                    "name": "Price",
                    "operators": list(PRICE_OPERATORS),
                    "unit": "inr",
                    "description": "Latest stored daily close in INR.",
                },
                {
                    "key": "price_change_percent",
                    "name": "Price change",
                    "operators": list(PERCENT_OPERATORS),
                    "unit": "percent",
                    "intervals": list(PRICE_INTERVALS),
                    "description": "Percent change between stored daily closes. A positive threshold with > is a rise. The same threshold with < is a fall.",
                },
            ]
        },
        "fundamental": _metrics(fundamentals),
        "technical": _metrics(technical),
        "pattern": {
            "types": list(PATTERN_TYPES),
            "statuses": list(PATTERN_STATUSES),
            "description": "Uses the latest stored daily pattern for that type. Developing and uncertain states cannot be alert targets.",
        },
        "repeat_modes": list(REPEAT_MODES),
    }


def _metrics(items: list[object]) -> list[dict[str, object]]:
    return [
        {
            "key": item.key,  # type: ignore[attr-defined]
            "name": item.name,  # type: ignore[attr-defined]
            "operators": sorted(item.operators),  # type: ignore[attr-defined]
            "unit": item.unit,  # type: ignore[attr-defined]
            "sector_benchmark": item.sector_benchmark,  # type: ignore[attr-defined]
            "event_kind": item.event_kind,  # type: ignore[attr-defined]
        }
        for item in items
    ]
