from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.api.market_errors import market_http_exception
from app.data_providers.market_data import get_market_data_provider
from app.data_providers.market_data.base import MarketDataProvider
from app.data_providers.market_data.errors import MarketDataError
from app.markets.calendar import MarketCalendar, get_market_calendar
from app.models import User
from app.schemas.market_data import MarketStatusResponse
from app.services.market_data_service import get_market_status

router = APIRouter(prefix="/api/markets", tags=["markets"])


@router.get("/{exchange}/status", response_model=MarketStatusResponse, summary="Indian market session")
def market_status(
    exchange: str,
    provider: MarketDataProvider = Depends(get_market_data_provider),
    calendar: MarketCalendar = Depends(get_market_calendar),
    _: User = Depends(get_current_user),
) -> MarketStatusResponse:
    """Return a session only when a provider or calendar source reports one."""
    try:
        return get_market_status(exchange, provider=provider, calendar=calendar)
    except MarketDataError as exc:
        raise market_http_exception(exc) from None
