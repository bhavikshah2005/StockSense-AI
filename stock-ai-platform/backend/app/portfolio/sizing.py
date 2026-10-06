"""Hypothetical long-only share count. This does not create a transaction."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_FLOOR

_LIMIT = Decimal("1000000000000")


class SizingError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class SizeResult:
    quantity: int
    position_value: Decimal
    per_share_risk: Decimal
    total_risk: Decimal
    capital_utilization_percent: Decimal
    binding_constraint: str
    risk_amount: Decimal
    assumptions: str


ASSUMPTIONS = (
    "Per-share risk is the entry price minus the stop price. "
    "Each limit uses floor division, so fractional shares are dropped. "
    "The quantity is the smallest limit that applies. "
    "Charges are not included. "
    "A stop price is a planning input, not an order. It may not execute, and a gap, slippage, or fee can make the loss larger."
)


def size_position(
    *,
    capital: Decimal,
    entry: Decimal,
    stop: Decimal,
    max_risk_inr: Decimal | None,
    max_risk_percent: Decimal | None,
    max_allocation_percent: Decimal | None,
    max_shares: int | None,
) -> SizeResult:
    _bounds(capital, entry, stop, max_risk_inr, max_risk_percent, max_allocation_percent, max_shares)
    per_share = entry - stop
    risk_amount = _risk_amount(capital, max_risk_inr, max_risk_percent)
    if risk_amount <= 0 or per_share <= 0:
        raise SizingError("invalid_risk")
    limits: list[tuple[str, int]] = [
        ("risk", _floor(risk_amount / per_share)),
        ("capital", _floor(capital / entry)),
    ]
    if max_allocation_percent is not None:
        limits.append(("allocation", _floor((capital * max_allocation_percent / Decimal("100")) / entry)))
    if max_shares is not None:
        limits.append(("share_cap", max_shares))
    binding, quantity = min(limits, key=lambda item: (item[1], _order(item[0])))
    if quantity < 1:
        raise SizingError("below_one_share")
    if quantity > 1_000_000_000:
        raise SizingError("overflow")
    value = (Decimal(quantity) * entry).quantize(Decimal("0.01"))
    total_risk = (Decimal(quantity) * per_share).quantize(Decimal("0.01"))
    utilization = (value / capital * Decimal("100")).quantize(Decimal("0.01"))
    return SizeResult(
        quantity=quantity,
        position_value=value,
        per_share_risk=per_share.quantize(Decimal("0.01")),
        total_risk=total_risk,
        capital_utilization_percent=utilization,
        binding_constraint=binding,
        risk_amount=risk_amount.quantize(Decimal("0.01")),
        assumptions=ASSUMPTIONS,
    )


def _risk_amount(capital: Decimal, amount: Decimal | None, percent: Decimal | None) -> Decimal:
    candidates: list[Decimal] = []
    if amount is not None:
        candidates.append(amount)
    if percent is not None:
        candidates.append(capital * percent / Decimal("100"))
    if not candidates:
        raise SizingError("missing_risk_limit")
    return min(candidates)


def _bounds(
    capital: Decimal,
    entry: Decimal,
    stop: Decimal,
    max_risk_inr: Decimal | None,
    max_risk_percent: Decimal | None,
    max_allocation_percent: Decimal | None,
    max_shares: int | None,
) -> None:
    if capital <= 0 or capital > _LIMIT or entry <= 0 or entry > _LIMIT:
        raise SizingError("invalid_price")
    if stop <= 0 or stop >= entry:
        raise SizingError("invalid_stop")
    if max_risk_inr is not None and (max_risk_inr <= 0 or max_risk_inr > _LIMIT):
        raise SizingError("invalid_risk")
    if max_risk_percent is not None and (max_risk_percent <= 0 or max_risk_percent > 100):
        raise SizingError("invalid_risk")
    if max_risk_inr is None and max_risk_percent is None:
        raise SizingError("missing_risk_limit")
    if max_allocation_percent is not None and (max_allocation_percent <= 0 or max_allocation_percent > 100):
        raise SizingError("invalid_allocation")
    if max_shares is not None and (max_shares < 1 or max_shares > 1_000_000_000):
        raise SizingError("invalid_share_cap")


def _floor(value: Decimal) -> int:
    if not value.is_finite():
        raise SizingError("overflow")
    return int(value.to_integral_value(rounding=ROUND_FLOOR))


def _order(name: str) -> int:
    return {"risk": 0, "capital": 1, "allocation": 2, "share_cap": 3}[name]
