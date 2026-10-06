"""User-owned watchlists. Authorization uses the session user, never a client user id."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.data_providers.market_data.base import MarketDataProvider
from app.data_providers.market_data.errors import MarketDataError
from app.models import Stock, User, Watchlist, WatchlistStock
from app.schemas.watchlist import (
    WatchlistDetail,
    WatchlistEntry,
    WatchlistListResponse,
    WatchlistQuote,
    WatchlistSummary,
)
from app.services.market_data_service import get_quote
from app.services.quote_cache import QuoteCache

NOT_FOUND = "not_found"
STOCK_NOT_FOUND = "stock_not_found"
DUPLICATE_NAME = "duplicate_name"
DUPLICATE_STOCK = "duplicate_stock"
TOO_MANY_LISTS = "too_many_lists"
TOO_MANY_STOCKS = "too_many_stocks"
INVALID_NAME = "invalid_name"
INVALID_DESCRIPTION = "invalid_description"
INVALID_ORDER = "invalid_order"

MESSAGES = {
    NOT_FOUND: "Watchlist not found",
    STOCK_NOT_FOUND: "Stock not found",
    DUPLICATE_NAME: "You already have a watchlist with that name",
    DUPLICATE_STOCK: "That stock is already on this watchlist",
    TOO_MANY_LISTS: "You have reached the watchlist limit",
    TOO_MANY_STOCKS: "This watchlist has reached its stock limit",
    INVALID_NAME: "Enter a watchlist name",
    INVALID_DESCRIPTION: "That description is too long",
    INVALID_ORDER: "The stock order does not match this watchlist",
}


class WatchlistError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code


def list_watchlists(db: Session, user: User, *, stock_id: UUID | None = None) -> WatchlistListResponse:
    if stock_id is not None:
        _require_stock(db, stock_id)
    rows = db.scalars(select(Watchlist).where(Watchlist.user_id == user.id).order_by(Watchlist.sort_order, Watchlist.created_at)).all()
    counts = _counts(db, [row.id for row in rows])
    membership = _membership(db, [row.id for row in rows], stock_id) if stock_id is not None else set()
    return WatchlistListResponse(
        results=[
            WatchlistSummary(
                id=row.id,
                name=row.name,
                description=row.description,
                is_default=row.is_default,
                stock_count=counts.get(row.id, 0),
                contains_stock=row.id in membership if stock_id is not None else None,
                created_at=row.created_at,
                updated_at=row.updated_at,
            )
            for row in rows
        ]
    )


def create_watchlist(db: Session, user: User, *, name: str, description: str | None) -> WatchlistSummary:
    cleaned = _name(name)
    note = _description(description)
    existing = db.scalar(select(func.count()).select_from(Watchlist).where(Watchlist.user_id == user.id)) or 0
    if int(existing) >= settings.watchlist_max_lists:
        raise WatchlistError(TOO_MANY_LISTS)
    _reject_duplicate_name(db, user.id, cleaned, ignore_id=None)
    has_default = db.scalar(select(Watchlist.id).where(Watchlist.user_id == user.id, Watchlist.is_default.is_(True)))
    row = Watchlist(
        user_id=user.id,
        name=cleaned,
        description=note,
        is_default=has_default is None,
        sort_order=int(existing),
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise WatchlistError(DUPLICATE_NAME) from None
    db.refresh(row)
    return _summary(row, 0, None)


def get_watchlist(
    db: Session,
    user: User,
    watchlist_id: UUID,
    *,
    provider: MarketDataProvider,
    cache: QuoteCache,
    ttl_seconds: int,
) -> WatchlistDetail:
    row = _owned(db, user, watchlist_id, with_entries=True)
    stocks = [_entry(db, entry, provider=provider, cache=cache, ttl_seconds=ttl_seconds) for entry in _ordered(row)]
    return WatchlistDetail(
        id=row.id,
        name=row.name,
        description=row.description,
        is_default=row.is_default,
        stock_count=len(stocks),
        created_at=row.created_at,
        updated_at=row.updated_at,
        stocks=stocks,
    )


def update_watchlist(
    db: Session,
    user: User,
    watchlist_id: UUID,
    *,
    name: str | None,
    description: str | None,
    update_description: bool,
) -> WatchlistSummary:
    row = _owned(db, user, watchlist_id, with_entries=False)
    if name is not None:
        cleaned = _name(name)
        _reject_duplicate_name(db, user.id, cleaned, ignore_id=row.id)
        row.name = cleaned
    if update_description:
        row.description = _description(description)
    row.updated_at = datetime.now(UTC)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise WatchlistError(DUPLICATE_NAME) from None
    db.refresh(row)
    count = db.scalar(select(func.count()).select_from(WatchlistStock).where(WatchlistStock.watchlist_id == row.id)) or 0
    return _summary(row, int(count), None)


def delete_watchlist(db: Session, user: User, watchlist_id: UUID) -> None:
    row = _owned(db, user, watchlist_id, with_entries=False)
    was_default = row.is_default
    db.delete(row)
    db.commit()
    if was_default:
        replacement = db.scalar(
            select(Watchlist).where(Watchlist.user_id == user.id).order_by(Watchlist.sort_order, Watchlist.created_at)
        )
        if replacement is not None:
            replacement.is_default = True
            replacement.updated_at = datetime.now(UTC)
            db.commit()


def add_stock(db: Session, user: User, watchlist_id: UUID, stock_id: UUID) -> WatchlistDetail:
    row = _owned(db, user, watchlist_id, with_entries=True)
    stock = _require_stock(db, stock_id)
    if any(entry.stock_id == stock.id for entry in row.entries):
        raise WatchlistError(DUPLICATE_STOCK)
    if len(row.entries) >= settings.watchlist_max_stocks:
        raise WatchlistError(TOO_MANY_STOCKS)
    next_order = max((entry.sort_order for entry in row.entries), default=-1) + 1
    db.add(WatchlistStock(watchlist_id=row.id, stock_id=stock.id, sort_order=next_order))
    row.updated_at = datetime.now(UTC)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise WatchlistError(DUPLICATE_STOCK) from None
    return _detail_without_quotes(db, user, watchlist_id)


def remove_stock(db: Session, user: User, watchlist_id: UUID, stock_id: UUID) -> None:
    row = _owned(db, user, watchlist_id, with_entries=True)
    match = next((entry for entry in row.entries if entry.stock_id == stock_id), None)
    if match is None:
        raise WatchlistError(STOCK_NOT_FOUND)
    db.delete(match)
    row.updated_at = datetime.now(UTC)
    db.commit()


def reorder_stocks(db: Session, user: User, watchlist_id: UUID, stock_ids: list[UUID]) -> WatchlistDetail:
    row = _owned(db, user, watchlist_id, with_entries=True)
    current = {entry.stock_id for entry in row.entries}
    if len(stock_ids) != len(current) or len(set(stock_ids)) != len(stock_ids) or set(stock_ids) != current:
        raise WatchlistError(INVALID_ORDER)
    positions = {stock_id: index for index, stock_id in enumerate(stock_ids)}
    now = datetime.now(UTC)
    for entry in row.entries:
        entry.sort_order = positions[entry.stock_id]
        entry.updated_at = now
    row.updated_at = now
    db.commit()
    return _detail_without_quotes(db, user, watchlist_id)


def set_default(db: Session, user: User, watchlist_id: UUID) -> WatchlistSummary:
    row = _owned(db, user, watchlist_id, with_entries=False)
    now = datetime.now(UTC)
    db.execute(
        update(Watchlist)
        .where(Watchlist.user_id == user.id, Watchlist.id != row.id)
        .values(is_default=False, updated_at=now)
    )
    db.flush()
    row.is_default = True
    row.updated_at = now
    db.commit()
    db.refresh(row)
    count = db.scalar(select(func.count()).select_from(WatchlistStock).where(WatchlistStock.watchlist_id == row.id)) or 0
    return _summary(row, int(count), None)


def _owned(db: Session, user: User, watchlist_id: UUID, *, with_entries: bool) -> Watchlist:
    statement = select(Watchlist).where(Watchlist.id == watchlist_id, Watchlist.user_id == user.id)
    if with_entries:
        statement = statement.options(selectinload(Watchlist.entries).selectinload(WatchlistStock.stock))
    row = db.scalar(statement)
    if row is None:
        raise WatchlistError(NOT_FOUND)
    return row


def _require_stock(db: Session, stock_id: UUID) -> Stock:
    stock = db.get(Stock, stock_id)
    if stock is None or not stock.is_active or stock.country != "IN" or stock.currency != "INR" or stock.exchange not in {"NSE", "BSE"}:
        raise WatchlistError(STOCK_NOT_FOUND)
    return stock


def _name(value: str) -> str:
    cleaned = " ".join(value.split())
    if not cleaned or len(cleaned) > settings.watchlist_name_max_length:
        raise WatchlistError(INVALID_NAME)
    return cleaned


def _description(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.split())
    if not cleaned:
        return None
    if len(cleaned) > settings.watchlist_description_max_length:
        raise WatchlistError(INVALID_DESCRIPTION)
    return cleaned


def _reject_duplicate_name(db: Session, user_id: UUID, name: str, *, ignore_id: UUID | None) -> None:
    statement = select(Watchlist.id).where(Watchlist.user_id == user_id, func.lower(Watchlist.name) == name.lower())
    if ignore_id is not None:
        statement = statement.where(Watchlist.id != ignore_id)
    if db.scalar(statement) is not None:
        raise WatchlistError(DUPLICATE_NAME)


def _counts(db: Session, watchlist_ids: list[UUID]) -> dict[UUID, int]:
    if not watchlist_ids:
        return {}
    rows = db.execute(
        select(WatchlistStock.watchlist_id, func.count())
        .where(WatchlistStock.watchlist_id.in_(watchlist_ids))
        .group_by(WatchlistStock.watchlist_id)
    ).all()
    return {watchlist_id: int(count) for watchlist_id, count in rows}


def _membership(db: Session, watchlist_ids: list[UUID], stock_id: UUID) -> set[UUID]:
    if not watchlist_ids:
        return set()
    rows = db.scalars(
        select(WatchlistStock.watchlist_id).where(
            WatchlistStock.watchlist_id.in_(watchlist_ids),
            WatchlistStock.stock_id == stock_id,
        )
    ).all()
    return set(rows)


def _ordered(row: Watchlist) -> list[WatchlistStock]:
    return sorted(row.entries, key=lambda entry: (entry.sort_order, entry.added_at, str(entry.id)))


def _summary(row: Watchlist, count: int, contains: bool | None) -> WatchlistSummary:
    return WatchlistSummary(
        id=row.id,
        name=row.name,
        description=row.description,
        is_default=row.is_default,
        stock_count=count,
        contains_stock=contains,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _detail_without_quotes(db: Session, user: User, watchlist_id: UUID) -> WatchlistDetail:
    row = _owned(db, user, watchlist_id, with_entries=True)
    stocks = []
    for entry in _ordered(row):
        stock = entry.stock
        stocks.append(
            WatchlistEntry(
                stock_id=stock.id,
                company_name=stock.company_name,
                symbol=stock.symbol,
                exchange=stock.exchange,
                isin=stock.isin,
                sector=stock.sector,
                industry=stock.industry,
                sort_order=entry.sort_order,
                added_at=entry.added_at,
                quote=WatchlistQuote(
                    available=False,
                    delayed=None,
                    source=None,
                    currency=None,
                    current_price=None,
                    previous_close=None,
                    change=None,
                    change_percent=None,
                    market_timestamp=None,
                    fetched_at=None,
                ),
            )
        )
    return WatchlistDetail(
        id=row.id,
        name=row.name,
        description=row.description,
        is_default=row.is_default,
        stock_count=len(stocks),
        created_at=row.created_at,
        updated_at=row.updated_at,
        stocks=stocks,
    )


def _entry(
    db: Session,
    entry: WatchlistStock,
    *,
    provider: MarketDataProvider,
    cache: QuoteCache,
    ttl_seconds: int,
) -> WatchlistEntry:
    stock = entry.stock
    quote = _quote(db, stock.id, provider=provider, cache=cache, ttl_seconds=ttl_seconds)
    return WatchlistEntry(
        stock_id=stock.id,
        company_name=stock.company_name,
        symbol=stock.symbol,
        exchange=stock.exchange,
        isin=stock.isin,
        sector=stock.sector,
        industry=stock.industry,
        sort_order=entry.sort_order,
        added_at=entry.added_at,
        quote=quote,
    )


def _quote(
    db: Session,
    stock_id: UUID,
    *,
    provider: MarketDataProvider,
    cache: QuoteCache,
    ttl_seconds: int,
) -> WatchlistQuote:
    try:
        body = get_quote(db, stock_id, provider=provider, cache=cache, ttl_seconds=ttl_seconds)
    except MarketDataError:
        return WatchlistQuote(
            available=False,
            delayed=None,
            source=None,
            currency=None,
            current_price=None,
            previous_close=None,
            change=None,
            change_percent=None,
            market_timestamp=None,
            fetched_at=None,
        )
    return WatchlistQuote(
        available=True,
        delayed=body.delayed,
        source=provider.name,
        currency=body.currency,
        current_price=format(body.current_price, "f"),
        previous_close=format(body.previous_close, "f") if body.previous_close is not None else None,
        change=format(body.change, "f") if body.change is not None else None,
        change_percent=format(body.change_percent, "f") if body.change_percent is not None else None,
        market_timestamp=body.market_timestamp,
        fetched_at=body.fetched_at,
    )
