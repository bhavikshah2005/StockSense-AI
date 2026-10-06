"""Coverage report for stored evidence.

This is not a stock rating. Missing inputs stay insufficient. They are not
treated as neutral, and no category is converted into a probability or a
buy, hold, or sell label. Version: coverage-1.
"""

from __future__ import annotations

SCORING_VERSION = "coverage-1"
_USABLE = {"met", "not_met"}
_TECHNICAL_INCLUDED = {"bullish_evidence", "bearish_evidence", "mixed_evidence", "no_clear_direction"}


def score_evidence(evidence: dict[str, object]) -> dict[str, object]:
    fundamental = _fundamental(evidence.get("fundamental"))
    technical = _technical(evidence.get("technical"))
    news = _news(evidence.get("news"))
    categories = {"fundamental": fundamental, "technical": technical, "news": news}
    included = [name for name, item in categories.items() if item["status"] == "included"]
    if not included:
        aggregate = "insufficient_data"
    elif len(included) < 3:
        aggregate = "partial"
    else:
        aggregate = "described"
    return {
        "version": SCORING_VERSION,
        "aggregate": aggregate,
        "numeric_score": None,
        "note": "No numeric stock score is calculated. A missing input is not treated as neutral or as low risk.",
        "categories": categories,
    }


def _fundamental(payload: object) -> dict[str, object]:
    rows = _rows(payload)
    usable = [row for row in rows if row.get("state") in _USABLE and row.get("stale") is not True]
    if len(usable) < 3:
        return {
            "status": "insufficient_data",
            "reason": "Fewer than three fresh fundamental or valuation comparisons are available.",
            "included": [row.get("metric_name") for row in usable],
            "excluded": [row.get("metric_name") for row in rows if row not in usable],
        }
    return {
        "status": "included",
        "reason": "Fresh threshold comparisons are listed. Meeting a threshold is not a valuation opinion.",
        "met": [row.get("metric_name") for row in usable if row.get("state") == "met"],
        "not_met": [row.get("metric_name") for row in usable if row.get("state") == "not_met"],
    }


def _technical(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict):
        return {"status": "insufficient_data", "reason": "No stored technical conclusion is available."}
    category = str(payload.get("category") or "")
    freshness = str(payload.get("freshness") or "")
    if freshness == "stale" or category not in _TECHNICAL_INCLUDED:
        return {
            "status": "insufficient_data",
            "reason": "The technical conclusion is missing, stale, or marked insufficient.",
            "category": category or None,
        }
    return {
        "status": "included",
        "reason": "The technical rubric category is copied from the existing detector. It is not a forecast.",
        "category": category,
        "conflicts": list(payload.get("conflicts") or []),
    }


def _news(payload: object) -> dict[str, object]:
    articles = payload if isinstance(payload, list) else []
    confirmed = [item for item in articles if isinstance(item, dict)]
    if not confirmed:
        return {"status": "insufficient_data", "reason": "No confirmed stored articles are linked to this stock."}
    counts = {"positive": 0, "negative": 0, "neutral": 0, "uncertain": 0, "unavailable": 0}
    for item in confirmed:
        label = item.get("sentiment") or "unavailable"
        if label not in counts:
            label = "unavailable"
        counts[str(label)] += 1
    return {
        "status": "included",
        "reason": "Counts of stored article sentiment. They do not predict a price move.",
        "article_count": len(confirmed),
        "sentiment_counts": counts,
    }


def _rows(payload: object) -> list[dict[str, object]]:
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]
