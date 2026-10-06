from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.data_providers.market_data import get_market_data_provider
from app.data_providers.market_data.base import MarketDataProvider
from app.models import User
from app.schemas.portfolio import (
    AllocationResponse,
    CashResponse,
    CashWrite,
    HistoryResponse,
    HoldingResponse,
    PortfolioListResponse,
    PortfolioResponse,
    PortfolioWrite,
    RiskSettingsResponse,
    RiskSettingsWrite,
    SizeRequest,
    SizeResponse,
    TransactionResponse,
    TransactionUpdate,
    TransactionWrite,
    ValuationResponse,
)
from app.services.portfolio_service import MESSAGES, PortfolioError, add_cash, add_transaction, calculate_size, create_portfolio, delete_cash, delete_portfolio, delete_transaction, get_risk_settings, list_cash, list_portfolios, list_transactions, save_risk_settings, set_archived, update_portfolio, update_transaction, valuation, value_history
from app.services.quote_cache import QuoteCache, get_quote_cache

router = APIRouter(prefix="/api/portfolios", tags=["portfolios"])

_STATUS = {
    "not_found": 404,
    "stock_not_found": 404,
    "duplicate_name": 409,
    "archived": 409,
    "insufficient_cash": 422,
    "insufficient_shares": 422,
    "invalid_stop": 422,
    "below_one_share": 422,
    "missing_risk_limit": 422,
}


def _portfolio(row) -> PortfolioResponse:
    return PortfolioResponse(
        id=row.id,
        name=row.name,
        description=row.description,
        currency=row.currency,
        contributed=row.total_capital,
        cash=row.available_cash,
        holding_count=len(row.holdings) if "holdings" in row.__dict__ else 0,
        archived_at=row.archived_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _raise(exc: PortfolioError) -> HTTPException:
    return HTTPException(status_code=_STATUS.get(exc.code, 422), detail=MESSAGES.get(exc.code, "The portfolio request is not valid."))


@router.get("", response_model=PortfolioListResponse, summary="List my portfolios")
def portfolios(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> PortfolioListResponse:
    rows = list_portfolios(db, user)
    return PortfolioListResponse(results=[_portfolio(row) for row in rows])


@router.post("", response_model=PortfolioResponse, status_code=201, summary="Create a portfolio")
def create(payload: PortfolioWrite, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> PortfolioResponse:
    try:
        row = create_portfolio(db, user, payload.name, payload.description)
    except PortfolioError as exc:
        raise _raise(exc) from None
    return _portfolio(row)


@router.get("/risk-settings", response_model=RiskSettingsResponse, summary="Read position-planning limits")
def read_risk(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> RiskSettingsResponse:
    row = get_risk_settings(db, user)
    if row is None:
        return RiskSettingsResponse(capital_inr=None, max_risk_inr=None, max_risk_percent=None, max_allocation_percent=None, max_shares=None)
    return RiskSettingsResponse(
        capital_inr=row.capital_inr,
        max_risk_inr=row.max_risk_inr,
        max_risk_percent=row.max_risk_percent,
        max_allocation_percent=row.max_allocation_percent,
        max_shares=row.max_shares,
    )


@router.put("/risk-settings", response_model=RiskSettingsResponse, summary="Save position-planning limits")
def write_risk(payload: RiskSettingsWrite, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> RiskSettingsResponse:
    try:
        row = save_risk_settings(db, user, **payload.model_dump())
    except PortfolioError as exc:
        raise _raise(exc) from None
    return RiskSettingsResponse(
        capital_inr=row.capital_inr,
        max_risk_inr=row.max_risk_inr,
        max_risk_percent=row.max_risk_percent,
        max_allocation_percent=row.max_allocation_percent,
        max_shares=row.max_shares,
    )


@router.post("/position-size", response_model=SizeResponse, summary="Calculate a hypothetical share count")
def position_size(payload: SizeRequest, user: User = Depends(get_current_user)) -> SizeResponse:
    del user
    try:
        return SizeResponse.model_validate(calculate_size(**payload.model_dump()))
    except PortfolioError as exc:
        raise _raise(exc) from None


@router.get("/{portfolio_id}", response_model=PortfolioResponse, summary="Get one portfolio")
def one(portfolio_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> PortfolioResponse:
    try:
        rows = [row for row in list_portfolios(db, user) if row.id == portfolio_id]
        if not rows:
            raise PortfolioError("not_found")
    except PortfolioError as exc:
        raise _raise(exc) from None
    return _portfolio(rows[0])


@router.patch("/{portfolio_id}", response_model=PortfolioResponse, summary="Rename a portfolio")
def rename(portfolio_id: UUID, payload: PortfolioWrite, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> PortfolioResponse:
    try:
        row = update_portfolio(db, user, portfolio_id, payload.name, payload.description)
    except PortfolioError as exc:
        raise _raise(exc) from None
    return _portfolio(row)


@router.post("/{portfolio_id}/archive", response_model=PortfolioResponse, summary="Archive a portfolio")
def archive(portfolio_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> PortfolioResponse:
    return _archive(db, user, portfolio_id, True)


@router.post("/{portfolio_id}/unarchive", response_model=PortfolioResponse, summary="Unarchive a portfolio")
def unarchive(portfolio_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> PortfolioResponse:
    return _archive(db, user, portfolio_id, False)


@router.delete("/{portfolio_id}", status_code=204, summary="Delete a portfolio and its records")
def remove(portfolio_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    try:
        delete_portfolio(db, user, portfolio_id)
    except PortfolioError as exc:
        raise _raise(exc) from None
    return Response(status_code=204)


@router.get("/{portfolio_id}/transactions", response_model=list[TransactionResponse], summary="List transactions")
def transactions(portfolio_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[TransactionResponse]:
    try:
        rows = list_transactions(db, user, portfolio_id)
    except PortfolioError as exc:
        raise _raise(exc) from None
    return [_transaction(row) for row in rows]


@router.post("/{portfolio_id}/transactions", response_model=TransactionResponse, status_code=201, summary="Add a buy or sell")
def create_transaction(
    portfolio_id: UUID,
    payload: TransactionWrite,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TransactionResponse:
    try:
        row = add_transaction(db, user, portfolio_id, **payload.model_dump())
    except PortfolioError as exc:
        raise _raise(exc) from None
    return _transaction(row)


@router.patch("/{portfolio_id}/transactions/{transaction_id}", response_model=TransactionResponse, summary="Edit a transaction")
def edit_transaction(
    portfolio_id: UUID,
    transaction_id: UUID,
    payload: TransactionUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TransactionResponse:
    try:
        row = update_transaction(db, user, portfolio_id, transaction_id, **payload.model_dump())
    except PortfolioError as exc:
        raise _raise(exc) from None
    return _transaction(row)


@router.delete("/{portfolio_id}/transactions/{transaction_id}", status_code=204, summary="Delete a transaction")
def remove_transaction(
    portfolio_id: UUID,
    transaction_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    try:
        delete_transaction(db, user, portfolio_id, transaction_id)
    except PortfolioError as exc:
        raise _raise(exc) from None
    return Response(status_code=204)


@router.get("/{portfolio_id}/cash", response_model=list[CashResponse], summary="List cash records")
def cash(portfolio_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[CashResponse]:
    try:
        rows = list_cash(db, user, portfolio_id)
    except PortfolioError as exc:
        raise _raise(exc) from None
    return [CashResponse(id=row.id, kind=row.kind, amount=row.amount, occurred_at=row.occurred_at, note=row.note) for row in rows]


@router.post("/{portfolio_id}/cash", response_model=CashResponse, status_code=201, summary="Record a deposit or withdrawal")
def create_cash(portfolio_id: UUID, payload: CashWrite, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> CashResponse:
    try:
        row = add_cash(db, user, portfolio_id, **payload.model_dump())
    except PortfolioError as exc:
        raise _raise(exc) from None
    return CashResponse(id=row.id, kind=row.kind, amount=row.amount, occurred_at=row.occurred_at, note=row.note)


@router.delete("/{portfolio_id}/cash/{movement_id}", status_code=204, summary="Delete a cash record")
def remove_cash(portfolio_id: UUID, movement_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    try:
        delete_cash(db, user, portfolio_id, movement_id)
    except PortfolioError as exc:
        raise _raise(exc) from None
    return Response(status_code=204)


@router.get("/{portfolio_id}/valuation", response_model=ValuationResponse, summary="Value holdings from stored transactions")
def value(
    portfolio_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    provider: MarketDataProvider = Depends(get_market_data_provider),
    cache: QuoteCache = Depends(get_quote_cache),
) -> ValuationResponse:
    try:
        payload = valuation(
            db,
            user,
            portfolio_id,
            provider=provider,
            cache=cache,
            ttl_seconds=settings.market_data_quote_ttl_seconds,
        )
    except PortfolioError as exc:
        raise _raise(exc) from None
    return ValuationResponse.model_validate(payload)


@router.get("/{portfolio_id}/holdings", response_model=list[HoldingResponse], summary="List derived holdings")
def holdings(
    portfolio_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    provider: MarketDataProvider = Depends(get_market_data_provider),
    cache: QuoteCache = Depends(get_quote_cache),
) -> list:
    body = value(portfolio_id, user, db, provider, cache)
    return body.holdings


@router.get("/{portfolio_id}/allocation", response_model=AllocationResponse, summary="Allocation by stock and sector")
def allocation(
    portfolio_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    provider: MarketDataProvider = Depends(get_market_data_provider),
    cache: QuoteCache = Depends(get_quote_cache),
) -> AllocationResponse:
    return value(portfolio_id, user, db, provider, cache).allocation


@router.get("/{portfolio_id}/history", response_model=HistoryResponse, summary="Holdings value from stored daily closes")
def history(portfolio_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> HistoryResponse:
    try:
        return HistoryResponse.model_validate(value_history(db, user, portfolio_id))
    except PortfolioError as exc:
        raise _raise(exc) from None


def _archive(db: Session, user: User, portfolio_id: UUID, archived: bool) -> PortfolioResponse:
    try:
        row = set_archived(db, user, portfolio_id, archived)
    except PortfolioError as exc:
        raise _raise(exc) from None
    return _portfolio(row)


def _transaction(row) -> TransactionResponse:
    return TransactionResponse(
        id=row.id,
        portfolio_id=row.portfolio_id,
        stock_id=row.stock_id,
        symbol=row.stock.symbol,
        exchange=row.stock.exchange,
        side=row.side,
        quantity=row.quantity,
        price=row.price,
        charges=row.charges,
        traded_at=row.traded_at,
        note=row.note,
    )
