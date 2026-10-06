"""Threshold precedence: user stock, user, sector, market, platform."""

from datetime import date, datetime

from app.metrics.evaluate import ResolvedThreshold
from app.models.metric_threshold import MetricThreshold
from app.models.stock import Stock


def resolve_threshold(
    rows: list[MetricThreshold],
    stock: Stock,
    *,
    as_of: date,
) -> tuple[MetricThreshold | None, ResolvedThreshold | None, list[str]]:
    active = [row for row in rows if row.is_active and _in_force(row, as_of)]
    skipped: list[str] = []
    buckets = (
        ("user_stock", [row for row in active if row.scope == "user" and row.stock_id == stock.id]),
        ("user", [row for row in active if row.scope == "user" and row.stock_id is None]),
        ("sector", _sector_rows(active, stock, skipped)),
        ("country", [row for row in active if row.scope == "country" and row.country == stock.country]),
        ("global", [row for row in active if row.scope == "global"]),
    )
    chosen_name = None
    chosen: list[MetricThreshold] = []
    for name, matches in buckets:
        if chosen:
            break
        if matches:
            chosen_name = name
            chosen = matches
        elif name == "user_stock":
            skipped.append("no user threshold for this stock")
        elif name == "user":
            skipped.append("no user threshold for all stocks")
        elif name == "sector" and "no sector on this stock" not in skipped:
            skipped.append("no sector threshold")
        elif name == "country":
            skipped.append("no India market threshold" if stock.country == "IN" else "no market threshold")
        elif name == "global":
            skipped.append("no platform threshold")
    if not chosen or chosen_name is None:
        return None, None, skipped
    ordered = sorted(chosen, key=lambda row: (row.updated_at, str(row.id)), reverse=True)
    row = ordered[0]
    reason = _reason(chosen_name, len(ordered) > 1, skipped)
    resolved = ResolvedThreshold(
        id=str(row.id),
        metric_key=row.metric_name,
        scope=_scope_label(row.scope),
        operator=row.operator.value if hasattr(row.operator, "value") else str(row.operator),
        basis=row.basis,
        threshold_value=row.threshold_value,
        threshold_high=row.threshold_high,
        definition_version=row.definition_version,
        effective_from=row.effective_from.isoformat() if row.effective_from else None,
        description=row.description,
        reason=reason,
        skipped=list(skipped),
    )
    return row, resolved, skipped


def _sector_rows(active: list[MetricThreshold], stock: Stock, skipped: list[str]) -> list[MetricThreshold]:
    if not stock.sector:
        skipped.append("no sector on this stock")
        return []
    return [
        row
        for row in active
        if row.scope == "sector" and row.sector == stock.sector and (row.country is None or row.country == stock.country)
    ]


def _in_force(row: MetricThreshold, as_of: date) -> bool:
    if row.effective_from is not None and row.effective_from > as_of:
        return False
    if row.effective_to is not None and row.effective_to < as_of:
        return False
    return True


def _scope_label(scope: object) -> str:
    value = scope.value if hasattr(scope, "value") else str(scope)
    return {"global": "platform", "country": "market", "sector": "sector", "user": "user"}.get(value, value)


def _reason(bucket: str, ambiguous: bool, skipped: list[str]) -> str:
    labels = {
        "user_stock": "Selected the user threshold for this stock.",
        "user": "Selected the user threshold. No stock-specific user threshold matched.",
        "sector": "Selected the sector threshold. No user threshold matched.",
        "country": "Selected the market threshold. No user or sector threshold matched.",
        "global": "Selected the platform default. No user, sector, or market threshold matched.",
    }
    text = labels[bucket]
    if ambiguous:
        text += " More than one active threshold shared this scope; the latest update was used."
    absent = [item for item in skipped if item.startswith("no ")]
    if absent and bucket != "user_stock":
        text += " Higher scopes that did not match: " + "; ".join(absent) + "."
    return text


def as_of_date(moment: datetime) -> date:
    return moment.date()
