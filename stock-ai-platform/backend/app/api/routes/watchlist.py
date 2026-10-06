from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.data_providers.market_data import get_market_data_provider
from app.data_providers.market_data.base import MarketDataProvider
from app.models import User
from app.schemas.watchlist import (
    WatchlistCreate,
    WatchlistDetail,
    WatchlistListResponse,
    WatchlistOrderUpdate,
    WatchlistStockCreate,
    WatchlistSummary,
    WatchlistUpdate,
)
from app.services.quote_cache import QuoteCache, get_quote_cache
from app.services.watchlist_service import (
    DUPLICATE_NAME,
    DUPLICATE_STOCK,
    INVALID_DESCRIPTION,
    INVALID_NAME,
    INVALID_ORDER,
    NOT_FOUND,
    STOCK_NOT_FOUND,
    TOO_MANY_LISTS,
    TOO_MANY_STOCKS,
    WatchlistError,
    add_stock,
    create_watchlist,
    delete_watchlist,
    get_watchlist,
    list_watchlists,
    remove_stock,
    reorder_stocks,
    set_default,
    update_watchlist,
)
from app.services.watchlist_service import MESSAGES

router = APIRouter(prefix="/api/watchlists", tags=["watchlists"])

_STATUS = {
    NOT_FOUND: 404,
    STOCK_NOT_FOUND: 404,
    DUPLICATE_NAME: 409,
    DUPLICATE_STOCK: 409,
    TOO_MANY_LISTS: 422,
    TOO_MANY_STOCKS: 422,
    INVALID_NAME: 422,
    INVALID_DESCRIPTION: 422,
    INVALID_ORDER: 422,
}


def _raise(exc: WatchlistError) -> HTTPException:
    return HTTPException(status_code=_STATUS.get(exc.code, 422), detail=MESSAGES[exc.code])


@router.get("", response_model=WatchlistListResponse, summary="List my watchlists")
def watchlists(
    stock_id: UUID | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> WatchlistListResponse:
    """Return watchlists owned by the signed-in user."""
    try:
        return list_watchlists(db, user, stock_id=stock_id)
    except WatchlistError as exc:
        raise _raise(exc) from None


@router.post("", response_model=WatchlistSummary, status_code=201, summary="Create a watchlist")
def create(
    payload: WatchlistCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> WatchlistSummary:
    """Create a named watchlist. The first list becomes the default."""
    try:
        return create_watchlist(db, user, name=payload.name, description=payload.description)
    except WatchlistError as exc:
        raise _raise(exc) from None


@router.get("/{watchlist_id}", response_model=WatchlistDetail, summary="Watchlist with quotes")
def detail(
    watchlist_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    provider: MarketDataProvider = Depends(get_market_data_provider),
    cache: QuoteCache = Depends(get_quote_cache),
) -> WatchlistDetail:
    """Return one owned watchlist. A missing quote stays unavailable."""
    try:
        return get_watchlist(
            db,
            user,
            watchlist_id,
            provider=provider,
            cache=cache,
            ttl_seconds=settings.market_data_quote_ttl_seconds,
        )
    except WatchlistError as exc:
        raise _raise(exc) from None


@router.patch("/{watchlist_id}", response_model=WatchlistSummary, summary="Rename a watchlist")
def update(
    watchlist_id: UUID,
    payload: WatchlistUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> WatchlistSummary:
    """Change the name or description of an owned watchlist."""
    try:
        return update_watchlist(
            db,
            user,
            watchlist_id,
            name=payload.name,
            description=payload.description,
            update_description="description" in payload.model_fields_set,
        )
    except WatchlistError as exc:
        raise _raise(exc) from None


@router.delete("/{watchlist_id}", status_code=204, summary="Delete a watchlist")
def delete(
    watchlist_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    """Delete an owned watchlist and its memberships. The stock records stay."""
    try:
        delete_watchlist(db, user, watchlist_id)
    except WatchlistError as exc:
        raise _raise(exc) from None
    return Response(status_code=204)


@router.post("/{watchlist_id}/stocks", response_model=WatchlistDetail, summary="Add a stock")
def add(
    watchlist_id: UUID,
    payload: WatchlistStockCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    provider: MarketDataProvider = Depends(get_market_data_provider),
    cache: QuoteCache = Depends(get_quote_cache),
) -> WatchlistDetail:
    """Add one Indian listing to an owned watchlist."""
    try:
        add_stock(db, user, watchlist_id, payload.stock_id)
        return get_watchlist(
            db,
            user,
            watchlist_id,
            provider=provider,
            cache=cache,
            ttl_seconds=settings.market_data_quote_ttl_seconds,
        )
    except WatchlistError as exc:
        raise _raise(exc) from None


@router.delete("/{watchlist_id}/stocks/{stock_id}", status_code=204, summary="Remove a stock")
def remove(
    watchlist_id: UUID,
    stock_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    """Remove a membership. The stock record stays."""
    try:
        remove_stock(db, user, watchlist_id, stock_id)
    except WatchlistError as exc:
        raise _raise(exc) from None
    return Response(status_code=204)


@router.patch("/{watchlist_id}/stocks/order", response_model=WatchlistDetail, summary="Reorder stocks")
def order(
    watchlist_id: UUID,
    payload: WatchlistOrderUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    provider: MarketDataProvider = Depends(get_market_data_provider),
    cache: QuoteCache = Depends(get_quote_cache),
) -> WatchlistDetail:
    """Replace the membership order. The list must contain each current stock once."""
    try:
        reorder_stocks(db, user, watchlist_id, payload.stock_ids)
        return get_watchlist(
            db,
            user,
            watchlist_id,
            provider=provider,
            cache=cache,
            ttl_seconds=settings.market_data_quote_ttl_seconds,
        )
    except WatchlistError as exc:
        raise _raise(exc) from None


@router.patch("/{watchlist_id}/default", response_model=WatchlistSummary, summary="Set the default watchlist")
def default(
    watchlist_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> WatchlistSummary:
    """Mark one owned watchlist as the only default."""
    try:
        return set_default(db, user, watchlist_id)
    except WatchlistError as exc:
        raise _raise(exc) from None
