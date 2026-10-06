"""Owned portfolios. Holdings and cash are derived from the ledger."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.data_providers.market_data.base import MarketDataProvider
from app.data_providers.market_data.errors import MarketDataError
from app.markets.time import IST
from app.models import Portfolio, PortfolioCashMovement, PortfolioHolding, PortfolioTransaction, Stock, StockPrice, User, UserRiskSettings
from app.portfolio.accounting import AccountingError, CashMove, Ledger, Position, Trade, replay
from app.portfolio.sizing import SizingError, size_position
from app.services.market_data_service import get_quote
from app.services.quote_cache import QuoteCache
from app.services.technical_service import STALE_DAYS

logger = logging.getLogger(__name__)

MAX_PORTFOLIOS = 20
MAX_TRANSACTIONS = 500
MAX_CASH = 200
NAME_LIMIT = 120
NOTE_LIMIT = 280
_FUTURE = timedelta(minutes=5)

NOT_FOUND = "not_found"
DUPLICATE_NAME = "duplicate_name"
INVALID_NAME = "invalid_name"
ARCHIVED = "archived"
STOCK_NOT_FOUND = "stock_not_found"
NOT_INDIAN = "not_indian"
INSUFFICIENT_CASH = "insufficient_cash"
INSUFFICIENT_SHARES = "insufficient_shares"
CHARGES_EXCEED = "charges_exceed_proceeds"
INVALID_QUANTITY = "invalid_quantity"
INVALID_PRICE = "invalid_price"
TOO_MANY = "too_many"
TOO_MANY_RECORDS = "too_many_records"
FUTURE_TIME = "future_time"
INVALID_AMOUNT = "invalid_amount"

MESSAGES = {
    NOT_FOUND: "Portfolio not found",
    DUPLICATE_NAME: "You already have a portfolio with that name.",
    INVALID_NAME: "Enter a portfolio name of 120 characters or fewer.",
    ARCHIVED: "This portfolio is archived. Unarchive it before adding records.",
    STOCK_NOT_FOUND: "Stock not found",
    NOT_INDIAN: "Only active NSE and BSE listings priced in INR can be added.",
    INSUFFICIENT_CASH: "This record would make cash negative. Cash starts at zero until you record a deposit.",
    INSUFFICIENT_SHARES: "The sell quantity is larger than the shares held at that time.",
    CHARGES_EXCEED: "Charges are larger than the sale proceeds.",
    INVALID_QUANTITY: "Quantity must be a positive whole number of shares.",
    INVALID_PRICE: "Enter a positive INR price.",
    TOO_MANY: "You can keep up to 20 portfolios.",
    TOO_MANY_RECORDS: "This portfolio has reached its record limit.",
    FUTURE_TIME: "The time cannot be in the future.",
    INVALID_AMOUNT: "Enter a positive INR amount.",
    "invalid_stop": "For a long position, the stop price must be below the entry price.",
    "missing_risk_limit": "Enter a maximum risk amount or a risk percentage.",
    "invalid_risk": "The risk limit is not valid.",
    "invalid_allocation": "The allocation limit must be between 0 and 100 percent.",
    "invalid_share_cap": "The share cap must be at least one share.",
    "below_one_share": "The limits allow fewer than one share.",
    "overflow": "The inputs are too large to calculate.",
}


class PortfolioError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def list_portfolios(db: Session, user: User) -> list[Portfolio]:
    return list(
        db.scalars(
            select(Portfolio)
            .where(Portfolio.user_id == user.id)
            .options(selectinload(Portfolio.holdings))
            .order_by(Portfolio.archived_at.is_(None).desc(), Portfolio.name)
        ).all()
    )


def create_portfolio(db: Session, user: User, name: str, description: str | None) -> Portfolio:
    cleaned, text_value = _names(name, description)
    count = db.scalar(select(func.count()).select_from(Portfolio).where(Portfolio.user_id == user.id)) or 0
    if count >= MAX_PORTFOLIOS:
        raise PortfolioError(TOO_MANY)
    row = Portfolio(user_id=user.id, name=cleaned, description=text_value, currency="INR")
    db.add(row)
    _commit_name(db)
    db.refresh(row)
    return row


def update_portfolio(db: Session, user: User, portfolio_id: UUID, name: str, description: str | None) -> Portfolio:
    row = _owned(db, user, portfolio_id, lock=True)
    cleaned, text_value = _names(name, description)
    row.name = cleaned
    row.description = text_value
    _commit_name(db)
    db.refresh(row)
    return row


def set_archived(db: Session, user: User, portfolio_id: UUID, archived: bool) -> Portfolio:
    row = _owned(db, user, portfolio_id, lock=True)
    row.archived_at = datetime.now(UTC) if archived else None
    db.commit()
    db.refresh(row)
    return row


def delete_portfolio(db: Session, user: User, portfolio_id: UUID) -> None:
    row = _owned(db, user, portfolio_id, lock=True)
    db.delete(row)
    db.commit()


def list_transactions(db: Session, user: User, portfolio_id: UUID) -> list[PortfolioTransaction]:
    _owned(db, user, portfolio_id, lock=False)
    return list(
        db.scalars(
            select(PortfolioTransaction)
            .where(PortfolioTransaction.portfolio_id == portfolio_id)
            .options(selectinload(PortfolioTransaction.stock))
            .order_by(PortfolioTransaction.traded_at.desc(), PortfolioTransaction.created_at.desc())
        ).all()
    )


def list_cash(db: Session, user: User, portfolio_id: UUID) -> list[PortfolioCashMovement]:
    _owned(db, user, portfolio_id, lock=False)
    return list(
        db.scalars(
            select(PortfolioCashMovement)
            .where(PortfolioCashMovement.portfolio_id == portfolio_id)
            .order_by(PortfolioCashMovement.occurred_at.desc())
        ).all()
    )


def add_transaction(
    db: Session,
    user: User,
    portfolio_id: UUID,
    *,
    stock_id: UUID,
    side: str,
    quantity: Decimal,
    price: Decimal,
    charges: Decimal,
    traded_at: datetime,
    note: str | None,
) -> PortfolioTransaction:
    portfolio = _editable(db, user, portfolio_id)
    stock = _indian_stock(db, stock_id)
    _time(traded_at)
    trades, moves = _books(db, portfolio.id)
    if len(trades) >= MAX_TRANSACTIONS:
        raise PortfolioError(TOO_MANY_RECORDS)
    row = PortfolioTransaction(
        id=uuid4(),
        portfolio_id=portfolio.id,
        stock_id=stock.id,
        side=side,
        quantity=quantity,
        price=price,
        charges=charges,
        traded_at=traded_at,
        note=_note(note),
    )
    trades.append(_trade(row))
    try:
        ledger = replay(trades, moves)
    except AccountingError as exc:
        raise PortfolioError(exc.code) from None
    db.add(row)
    _sync(db, portfolio, ledger)
    db.commit()
    db.refresh(row)
    return row


def update_transaction(
    db: Session,
    user: User,
    portfolio_id: UUID,
    transaction_id: UUID,
    *,
    quantity: Decimal,
    price: Decimal,
    charges: Decimal,
    traded_at: datetime,
    note: str | None,
) -> PortfolioTransaction:
    portfolio = _editable(db, user, portfolio_id)
    row = db.get(PortfolioTransaction, transaction_id)
    if row is None or row.portfolio_id != portfolio.id:
        raise PortfolioError(NOT_FOUND)
    _time(traded_at)
    row.quantity = quantity
    row.price = price
    row.charges = charges
    row.traded_at = traded_at
    row.note = _note(note)
    _restate(db, portfolio)
    db.commit()
    db.refresh(row)
    return row


def delete_transaction(db: Session, user: User, portfolio_id: UUID, transaction_id: UUID) -> None:
    portfolio = _editable(db, user, portfolio_id)
    row = db.get(PortfolioTransaction, transaction_id)
    if row is None or row.portfolio_id != portfolio.id:
        raise PortfolioError(NOT_FOUND)
    db.delete(row)
    db.flush()
    _restate(db, portfolio)
    db.commit()


def add_cash(
    db: Session,
    user: User,
    portfolio_id: UUID,
    *,
    kind: str,
    amount: Decimal,
    occurred_at: datetime,
    note: str | None,
) -> PortfolioCashMovement:
    portfolio = _editable(db, user, portfolio_id)
    _time(occurred_at)
    trades, moves = _books(db, portfolio.id)
    if len(moves) >= MAX_CASH:
        raise PortfolioError(TOO_MANY_RECORDS)
    row = PortfolioCashMovement(
        id=uuid4(),
        portfolio_id=portfolio.id,
        kind=kind,
        amount=amount,
        occurred_at=occurred_at,
        note=_note(note),
    )
    moves.append(_move(row))
    try:
        ledger = replay(trades, moves)
    except AccountingError as exc:
        raise PortfolioError(exc.code) from None
    db.add(row)
    _sync(db, portfolio, ledger)
    db.commit()
    db.refresh(row)
    return row


def delete_cash(db: Session, user: User, portfolio_id: UUID, movement_id: UUID) -> None:
    portfolio = _editable(db, user, portfolio_id)
    row = db.get(PortfolioCashMovement, movement_id)
    if row is None or row.portfolio_id != portfolio.id:
        raise PortfolioError(NOT_FOUND)
    db.delete(row)
    db.flush()
    _restate(db, portfolio)
    db.commit()


def valuation(
    db: Session,
    user: User,
    portfolio_id: UUID,
    *,
    provider: MarketDataProvider,
    cache: QuoteCache,
    ttl_seconds: int,
    now: datetime | None = None,
) -> dict[str, object]:
    portfolio = _owned(db, user, portfolio_id, lock=False)
    moment = now or datetime.now(UTC)
    ledger = _ledger(db, portfolio.id)
    quotes = _quotes(db, list(ledger.positions), provider=provider, cache=cache, ttl_seconds=ttl_seconds, now=moment)
    stocks = _stocks(db, list(ledger.positions))
    holdings = []
    market = Decimal("0.00")
    cost = Decimal("0.00")
    priced = True
    for stock_id, position in ledger.positions.items():
        stock = stocks[stock_id]
        quote = quotes.get(stock_id)
        row = _holding_view(stock, position, quote, moment)
        holdings.append(row)
        cost += position.cost
        if row["market_value"] is None:
            priced = False
        else:
            market += row["market_value"]
    unrealized = None if not priced else (market - cost).quantize(Decimal("0.01"))
    total = None if unrealized is None else (ledger.realized + unrealized).quantize(Decimal("0.01"))
    return {
        "portfolio_id": portfolio.id,
        "currency": "INR",
        "cash": ledger.cash,
        "contributed": ledger.contributed,
        "cost_basis": cost.quantize(Decimal("0.01")),
        "market_value": None if not priced else market.quantize(Decimal("0.01")),
        "realized_pnl": ledger.realized,
        "unrealized_pnl": unrealized,
        "total_pnl": total,
        "valuation_complete": priced,
        "holdings_only": True,
        "basis": "Total P&L is realized gain plus unrealized gain. Unrealized gain is market value minus remaining cost. Cash is not included in market value.",
        "benchmark": None,
        "benchmark_note": "No index series is stored, so this portfolio is not compared with a benchmark.",
        "as_of": moment,
        "holdings": holdings,
        "allocation": _allocation(holdings),
    }


def value_history(db: Session, user: User, portfolio_id: UUID) -> dict[str, object]:
    portfolio = _owned(db, user, portfolio_id, lock=False)
    trades = list(db.scalars(select(PortfolioTransaction).where(PortfolioTransaction.portfolio_id == portfolio.id)).all())
    if not trades:
        return {"status": "insufficient_data", "message": "No transactions are stored, so there is no holdings value history.", "points": []}
    stock_ids = {row.stock_id for row in trades}
    bars = list(
        db.scalars(
            select(StockPrice).where(StockPrice.stock_id.in_(stock_ids), StockPrice.interval == "1d").order_by(StockPrice.timestamp)
        ).all()
    )
    closes: dict[tuple[UUID, object], Decimal] = {}
    for bar in bars:
        closes[(bar.stock_id, bar.timestamp.astimezone(IST).date())] = bar.close
    days = sorted({row.traded_at.astimezone(IST).date() for row in trades} | {bar.timestamp.astimezone(IST).date() for bar in bars})
    points = []
    for day in days:
        quantities: dict[UUID, Decimal] = {}
        for row in trades:
            if row.traded_at.astimezone(IST).date() > day:
                continue
            signed = row.quantity if row.side == "buy" else -row.quantity
            quantities[row.stock_id] = quantities.get(row.stock_id, Decimal("0")) + signed
        active = {stock_id: qty for stock_id, qty in quantities.items() if qty > 0}
        if not active:
            continue
        if any((stock_id, day) not in closes for stock_id in active):
            return {
                "status": "insufficient_data",
                "message": "Stored daily closes do not cover every day a holding was open, so a value history is not shown.",
                "points": [],
            }
        value = sum((qty * closes[(stock_id, day)] for stock_id, qty in active.items()), Decimal("0"))
        points.append({"date": day.isoformat(), "holdings_value": value.quantize(Decimal("0.01"))})
    if not points:
        return {"status": "insufficient_data", "message": "Stored daily closes do not cover these holdings.", "points": []}
    return {
        "status": "complete",
        "message": "Each point is the sum of shares held that day times the stored daily close. Cash is not included.",
        "points": points,
    }


def get_risk_settings(db: Session, user: User) -> UserRiskSettings | None:
    return db.get(UserRiskSettings, user.id)


def save_risk_settings(
    db: Session,
    user: User,
    *,
    capital_inr: Decimal | None,
    max_risk_inr: Decimal | None,
    max_risk_percent: Decimal | None,
    max_allocation_percent: Decimal | None,
    max_shares: int | None,
) -> UserRiskSettings:
    row = db.get(UserRiskSettings, user.id)
    if row is None:
        row = UserRiskSettings(user_id=user.id)
        db.add(row)
    row.capital_inr = capital_inr
    row.max_risk_inr = max_risk_inr
    row.max_risk_percent = max_risk_percent
    row.max_allocation_percent = max_allocation_percent
    row.max_shares = max_shares
    db.commit()
    db.refresh(row)
    return row


def calculate_size(**kwargs: object) -> dict[str, object]:
    try:
        result = size_position(**kwargs)  # type: ignore[arg-type]
    except SizingError as exc:
        raise PortfolioError(exc.code) from None
    return {
        "quantity": result.quantity,
        "position_value": result.position_value,
        "per_share_risk": result.per_share_risk,
        "total_risk": result.total_risk,
        "capital_utilization_percent": result.capital_utilization_percent,
        "binding_constraint": result.binding_constraint,
        "risk_amount": result.risk_amount,
        "assumptions": result.assumptions,
        "warning": "This quantity is not a trade instruction and is not added to a portfolio.",
    }


def _restate(db: Session, portfolio: Portfolio) -> None:
    try:
        ledger = _ledger(db, portfolio.id)
    except AccountingError as exc:
        db.rollback()
        raise PortfolioError(exc.code) from None
    _sync(db, portfolio, ledger)


def _ledger(db: Session, portfolio_id: UUID) -> Ledger:
    trades, moves = _books(db, portfolio_id)
    return replay(trades, moves)


def _books(db: Session, portfolio_id: UUID) -> tuple[list[Trade], list[CashMove]]:
    trades = [
        _trade(row)
        for row in db.scalars(select(PortfolioTransaction).where(PortfolioTransaction.portfolio_id == portfolio_id)).all()
    ]
    moves = [
        _move(row)
        for row in db.scalars(select(PortfolioCashMovement).where(PortfolioCashMovement.portfolio_id == portfolio_id)).all()
    ]
    return trades, moves


def _sync(db: Session, portfolio: Portfolio, ledger: Ledger) -> None:
    existing = {row.stock_id: row for row in db.scalars(select(PortfolioHolding).where(PortfolioHolding.portfolio_id == portfolio.id)).all()}
    seen: set[UUID] = set()
    for stock_id, position in ledger.positions.items():
        key = UUID(stock_id)
        seen.add(key)
        average = (position.cost / position.quantity).quantize(Decimal("0.0001"))
        row = existing.get(key)
        if row is None:
            db.add(
                PortfolioHolding(
                    portfolio_id=portfolio.id,
                    stock_id=key,
                    quantity=position.quantity,
                    average_buy_price=average,
                    cost_basis=position.cost,
                )
            )
        else:
            row.quantity = position.quantity
            row.average_buy_price = average
            row.cost_basis = position.cost
    for key, row in existing.items():
        if key not in seen:
            db.delete(row)
    portfolio.available_cash = ledger.cash
    portfolio.total_capital = ledger.contributed


def _quotes(
    db: Session,
    stock_ids: list[str],
    *,
    provider: MarketDataProvider,
    cache: QuoteCache,
    ttl_seconds: int,
    now: datetime,
) -> dict[str, object]:
    found: dict[str, object] = {}
    for stock_id in stock_ids:
        try:
            found[stock_id] = get_quote(db, UUID(stock_id), provider=provider, cache=cache, ttl_seconds=ttl_seconds, now=now)
        except MarketDataError:
            logger.info("portfolio quote unavailable stock_id=%s", stock_id)
            found[stock_id] = None
    return found


def _holding_view(stock: Stock, position: Position, quote: object, now: datetime) -> dict[str, object]:
    price = None
    timestamp = None
    state = "unavailable"
    delayed = None
    delay_minutes = None
    if quote is not None:
        price = quote.current_price
        timestamp = quote.market_timestamp
        delayed = quote.delayed
        delay_minutes = quote.delay_minutes
        age = timestamp.astimezone(IST).date() < now.astimezone(IST).date() - timedelta(days=STALE_DAYS)
        if age:
            state = "stale"
        elif delayed:
            state = "delayed"
        else:
            state = "last_available"
    usable = price is not None and state not in {"unavailable", "stale"}
    market = None if not usable else (position.quantity * price).quantize(Decimal("0.01"))
    unrealized = None if market is None else (market - position.cost).quantize(Decimal("0.01"))
    percent = None
    if unrealized is not None and position.cost > 0:
        percent = (unrealized / position.cost * Decimal("100")).quantize(Decimal("0.01"))
    return {
        "stock_id": stock.id,
        "symbol": stock.symbol,
        "exchange": stock.exchange,
        "company_name": stock.company_name,
        "sector": stock.sector,
        "quantity": position.quantity,
        "average_cost": (position.cost / position.quantity).quantize(Decimal("0.0001")),
        "cost_basis": position.cost,
        "realized_pnl": position.realized,
        "last_price": price,
        "market_value": market,
        "unrealized_pnl": unrealized,
        "unrealized_pnl_percent": percent,
        "price_timestamp": None if state == "unavailable" else timestamp,
        "price_state": state,
        "delayed": delayed,
        "delay_minutes": delay_minutes,
    }


def _allocation(holdings: list[dict[str, object]]) -> dict[str, object]:
    valued = [row for row in holdings if isinstance(row["market_value"], Decimal)]
    missing = [row["symbol"] for row in holdings if row["market_value"] is None]
    total = sum((row["market_value"] for row in valued), Decimal("0"))
    by_stock = []
    sectors: dict[str, Decimal] = {}
    missing_sector = False
    for row in valued:
        assert isinstance(row["market_value"], Decimal)
        weight = Decimal("0.00") if total == 0 else (row["market_value"] / total * Decimal("100")).quantize(Decimal("0.01"))
        by_stock.append({"symbol": row["symbol"], "stock_id": row["stock_id"], "market_value": row["market_value"], "weight_percent": weight})
        sector = row["sector"] if isinstance(row["sector"], str) and row["sector"].strip() else None
        if sector is None:
            missing_sector = True
            sector = "Sector not stored"
        sectors[sector] = sectors.get(sector, Decimal("0.00")) + row["market_value"]
    by_sector = []
    for name, value in sorted(sectors.items()):
        weight = Decimal("0.00") if total == 0 else (value / total * Decimal("100")).quantize(Decimal("0.01"))
        by_sector.append({"sector": name, "market_value": value, "weight_percent": weight})
    status = "complete"
    if not valued:
        status = "insufficient_data"
    elif missing or missing_sector:
        status = "partial"
    return {"status": status, "by_stock": by_stock, "by_sector": by_sector, "unpriced_symbols": missing}


def _stocks(db: Session, stock_ids: list[str]) -> dict[str, Stock]:
    if not stock_ids:
        return {}
    rows = db.scalars(select(Stock).where(Stock.id.in_([UUID(item) for item in stock_ids]))).all()
    return {str(row.id): row for row in rows}


def _owned(db: Session, user: User, portfolio_id: UUID, *, lock: bool) -> Portfolio:
    statement = select(Portfolio).where(Portfolio.id == portfolio_id, Portfolio.user_id == user.id)
    if lock:
        statement = statement.with_for_update()
    row = db.scalar(statement)
    if row is None:
        raise PortfolioError(NOT_FOUND)
    return row


def _editable(db: Session, user: User, portfolio_id: UUID) -> Portfolio:
    row = _owned(db, user, portfolio_id, lock=True)
    if row.archived_at is not None:
        raise PortfolioError(ARCHIVED)
    return row


def _indian_stock(db: Session, stock_id: UUID) -> Stock:
    stock = db.get(Stock, stock_id)
    if stock is None or not stock.is_active:
        raise PortfolioError(STOCK_NOT_FOUND)
    if stock.country != "IN" or stock.currency != "INR" or stock.exchange not in {"NSE", "BSE"}:
        raise PortfolioError(NOT_INDIAN)
    return stock


def _names(name: str, description: str | None) -> tuple[str, str | None]:
    cleaned = " ".join(name.split())
    if not cleaned or len(cleaned) > NAME_LIMIT:
        raise PortfolioError(INVALID_NAME)
    text_value = None if description is None else " ".join(description.split())
    if text_value == "":
        text_value = None
    if text_value is not None and len(text_value) > NOTE_LIMIT:
        raise PortfolioError(INVALID_NAME)
    return cleaned, text_value


def _note(note: str | None) -> str | None:
    if note is None:
        return None
    cleaned = " ".join(note.split())
    if cleaned == "":
        return None
    if len(cleaned) > NOTE_LIMIT:
        raise PortfolioError(INVALID_NAME)
    return cleaned


def _time(moment: datetime) -> None:
    if moment.tzinfo is None or moment > datetime.now(UTC) + _FUTURE:
        raise PortfolioError(FUTURE_TIME)


def _trade(row: PortfolioTransaction) -> Trade:
    return Trade(str(row.id), str(row.stock_id), row.side, row.quantity, row.price, row.charges, row.traded_at)


def _move(row: PortfolioCashMovement) -> CashMove:
    return CashMove(str(row.id), row.kind, row.amount, row.occurred_at)


def _commit_name(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise PortfolioError(DUPLICATE_NAME) from None
