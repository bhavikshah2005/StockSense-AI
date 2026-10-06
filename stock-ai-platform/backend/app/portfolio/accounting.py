"""Weighted-average cost for long-only Indian cash equities.

Transactions are the source of truth. A buy adds quantity and adds
price times quantity plus charges to cost. A sell removes the average
cost of the shares sold. Charges on a sell reduce the proceeds.
Cash starts at zero and changes only through deposits, withdrawals, and trades.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

MONEY = Decimal("0.01")
_RANK = {"deposit": 0, "buy": 1, "sell": 2, "withdrawal": 3}


class AccountingError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class Trade:
    id: str
    stock_id: str
    side: str
    quantity: Decimal
    price: Decimal
    charges: Decimal
    at: datetime


@dataclass(frozen=True)
class CashMove:
    id: str
    kind: str
    amount: Decimal
    at: datetime


@dataclass
class Position:
    quantity: Decimal
    cost: Decimal
    realized: Decimal


@dataclass
class Ledger:
    positions: dict[str, Position]
    cash: Decimal
    contributed: Decimal
    realized: Decimal


def replay(trades: list[Trade], cash_moves: list[CashMove]) -> Ledger:
    events: list[tuple[datetime, int, str, str, Trade | CashMove]] = []
    for trade in trades:
        events.append((trade.at, _RANK[trade.side], trade.id, "trade", trade))
    for move in cash_moves:
        events.append((move.at, _RANK[move.kind], move.id, "cash", move))
    events.sort(key=lambda item: (item[0], item[1], item[2]))
    positions: dict[str, Position] = {}
    cash = Decimal("0.00")
    contributed = Decimal("0.00")
    closed = Decimal("0.00")
    for _at, _rank, _id, kind, event in events:
        if kind == "cash":
            assert isinstance(event, CashMove)
            cash, contributed = _cash(cash, contributed, event)
        else:
            assert isinstance(event, Trade)
            cash, closed = _trade(positions, cash, closed, event)
    realized = closed + sum((item.realized for item in positions.values()), Decimal("0.00"))
    return Ledger(positions=positions, cash=_money(cash), contributed=_money(contributed), realized=_money(realized))


def _cash(cash: Decimal, contributed: Decimal, move: CashMove) -> tuple[Decimal, Decimal]:
    amount = _money(move.amount)
    if amount <= 0:
        raise AccountingError("invalid_amount")
    if move.kind == "deposit":
        return cash + amount, contributed + amount
    if amount > cash:
        raise AccountingError("insufficient_cash")
    return cash - amount, contributed - amount


def _trade(positions: dict[str, Position], cash: Decimal, closed: Decimal, trade: Trade) -> tuple[Decimal, Decimal]:
    quantity = trade.quantity
    if quantity != quantity.to_integral_value() or quantity <= 0:
        raise AccountingError("invalid_quantity")
    price = trade.price
    charges = _money(trade.charges)
    if price <= 0 or charges < 0:
        raise AccountingError("invalid_price")
    position = positions.get(trade.stock_id, Position(Decimal("0"), Decimal("0.00"), Decimal("0.00")))
    if trade.side == "buy":
        outflow = _money(quantity * price + charges)
        if outflow > cash:
            raise AccountingError("insufficient_cash")
        position.cost = _money(position.cost + outflow)
        position.quantity += quantity
        positions[trade.stock_id] = position
        return cash - outflow, closed
    if quantity > position.quantity:
        raise AccountingError("insufficient_shares")
    proceeds = _money(quantity * price - charges)
    if proceeds < 0:
        raise AccountingError("charges_exceed_proceeds")
    removed = position.cost if quantity == position.quantity else _money(position.cost * quantity / position.quantity)
    gain = _money(proceeds - removed)
    position.quantity -= quantity
    position.cost = _money(position.cost - removed)
    if position.quantity == 0:
        closed = _money(closed + position.realized + gain)
        positions.pop(trade.stock_id, None)
    else:
        position.realized = _money(position.realized + gain)
        positions[trade.stock_id] = position
    return cash + proceeds, closed


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)
