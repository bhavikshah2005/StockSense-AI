from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.fundamental_errors import fundamental_http_exception
from app.api.market_errors import market_http_exception
from app.core.config import settings
from app.core.database import get_db
from app.data_providers.fundamentals import get_fundamental_data_provider
from app.data_providers.fundamentals.base import FundamentalDataProvider
from app.data_providers.fundamentals.errors import FundamentalDataError
from app.data_providers.market_data.base import MarketDataProvider
from app.data_providers.market_data.errors import MarketDataError
from app.data_providers.market_data import get_market_data_provider
from app.models import User
from app.schemas.fundamentals import (
    FundamentalHistoryResponse,
    FundamentalReportResponse,
    SectorComparisonResponse,
    ValuationHistoryResponse,
    ValuationResponse,
)
from app.schemas.market_data import HistoryResponse, PriceHistoryResponse, QuoteResponse
from app.schemas.technical import PatternHistoryResponse, TechnicalAnalysisResponse, TechnicalSummaryResponse
from app.schemas.stock import StockDetail, StockSearchResponse
from app.services.fundamental_cache import FundamentalCache, get_fundamental_cache
from app.services.fundamental_service import (
    get_fundamental_history,
    get_latest_fundamentals,
    get_latest_valuation,
    get_sector_comparison,
    get_valuation_history,
)
from app.services.history_cache import HistoryCache, get_history_cache
from app.services.history_service import get_history
from app.services.market_data_service import get_quote, get_stock_detail, list_prices
from app.services.quote_cache import QuoteCache, get_quote_cache
from app.services.stock_service import search_stocks
from app.services.technical_cache import TechnicalCache, get_technical_cache
from app.services.technical_service import get_pattern_history, get_technical_analysis, get_technical_summary

router = APIRouter(prefix="/api/stocks", tags=["stocks"])


@router.get("/search", response_model=StockSearchResponse, summary="Search Indian listings")
def search(
    q: str = Query(min_length=1, max_length=64),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> StockSearchResponse:
    """Search NSE and BSE names, symbols, and ISINs for the active market."""
    if not q.strip():
        raise HTTPException(status_code=422, detail="Query is required")
    return search_stocks(db, q)


@router.get("/{stock_id}", response_model=StockDetail, summary="Indian listing")
def stock_detail(
    stock_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> StockDetail:
    """Return one NSE or BSE listing. This response has no prices."""
    try:
        return get_stock_detail(db, stock_id)
    except MarketDataError as exc:
        raise market_http_exception(exc) from None


@router.get("/{stock_id}/quote", response_model=QuoteResponse, summary="Latest Indian quote")
def quote(
    stock_id: UUID,
    db: Session = Depends(get_db),
    provider: MarketDataProvider = Depends(get_market_data_provider),
    cache: QuoteCache = Depends(get_quote_cache),
    _: User = Depends(get_current_user),
) -> QuoteResponse:
    """Return a cached quote, or the provider quote when the cache is empty."""
    try:
        return get_quote(
            db,
            stock_id,
            provider=provider,
            cache=cache,
            ttl_seconds=settings.market_data_quote_ttl_seconds,
        )
    except MarketDataError as exc:
        raise market_http_exception(exc) from None


@router.get("/{stock_id}/history", response_model=HistoryResponse, summary="Indian price history")
def history(
    stock_id: UUID,
    range: str | None = Query(default=None, max_length=8),
    start_date: date | None = None,
    end_date: date | None = None,
    interval: str | None = Query(default=None, max_length=8),
    db: Session = Depends(get_db),
    provider: MarketDataProvider = Depends(get_market_data_provider),
    cache: HistoryCache = Depends(get_history_cache),
    _: User = Depends(get_current_user),
) -> HistoryResponse:
    """Return stored bars for a chart range, syncing only spans PostgreSQL does not already cover."""
    try:
        return get_history(
            db,
            stock_id,
            provider=provider,
            cache=cache,
            ttl_seconds=settings.market_data_history_ttl_seconds,
            max_years=settings.market_data_max_history_years,
            range_name=range,
            start=start_date,
            end=end_date,
            interval=interval,
        )
    except MarketDataError as exc:
        raise market_http_exception(exc) from None


@router.get("/{stock_id}/prices", response_model=PriceHistoryResponse, summary="Stored OHLCV bars")
def prices(
    stock_id: UUID,
    interval: str = Query(default="1d", min_length=2, max_length=8),
    start: date | None = None,
    end: date | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> PriceHistoryResponse:
    """Return bars already stored for this listing. This route does not call a provider."""
    try:
        return list_prices(db, stock_id, interval=interval, start=start, end=end)
    except MarketDataError as exc:
        raise market_http_exception(exc) from None


@router.get("/{stock_id}/fundamentals", response_model=FundamentalReportResponse, summary="Latest reported fundamentals")
def fundamentals(
    stock_id: UUID,
    db: Session = Depends(get_db),
    provider: FundamentalDataProvider = Depends(get_fundamental_data_provider),
    cache: FundamentalCache = Depends(get_fundamental_cache),
    _: User = Depends(get_current_user),
) -> FundamentalReportResponse:
    """Return the newest stored financial report. A missing provider does not invent figures."""
    try:
        return get_latest_fundamentals(
            db,
            stock_id,
            provider=provider,
            cache=cache,
            ttl_seconds=settings.fundamental_cache_ttl_seconds,
            stale_hours=settings.fundamental_report_stale_hours,
        )
    except MarketDataError as exc:
        raise market_http_exception(exc) from None
    except FundamentalDataError as exc:
        raise fundamental_http_exception(exc) from None


@router.get(
    "/{stock_id}/fundamentals/history",
    response_model=FundamentalHistoryResponse,
    summary="Reported fundamental history",
)
def fundamental_history(
    stock_id: UUID,
    start_date: date | None = None,
    end_date: date | None = None,
    period: str | None = Query(default=None, pattern="^(annual|quarterly)$"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=10000),
    db: Session = Depends(get_db),
    provider: FundamentalDataProvider = Depends(get_fundamental_data_provider),
    cache: FundamentalCache = Depends(get_fundamental_cache),
    _: User = Depends(get_current_user),
) -> FundamentalHistoryResponse:
    """Return reported periods in chronological order."""
    if start_date is not None and end_date is not None and start_date > end_date:
        raise HTTPException(status_code=422, detail="start_date must be on or before end_date")
    try:
        return get_fundamental_history(
            db,
            stock_id,
            provider=provider,
            cache=cache,
            ttl_seconds=settings.fundamental_cache_ttl_seconds,
            stale_hours=settings.fundamental_report_stale_hours,
            start=start_date,
            end=end_date,
            period=period,
            limit=limit,
            offset=offset,
        )
    except MarketDataError as exc:
        raise market_http_exception(exc) from None
    except FundamentalDataError as exc:
        raise fundamental_http_exception(exc) from None


@router.get("/{stock_id}/valuation", response_model=ValuationResponse, summary="Latest valuation snapshot")
def valuation(
    stock_id: UUID,
    db: Session = Depends(get_db),
    provider: FundamentalDataProvider = Depends(get_fundamental_data_provider),
    cache: FundamentalCache = Depends(get_fundamental_cache),
    _: User = Depends(get_current_user),
) -> ValuationResponse:
    """Return the newest point-in-time valuation. Multiples are not copied onto the financial report."""
    try:
        return get_latest_valuation(
            db,
            stock_id,
            provider=provider,
            cache=cache,
            ttl_seconds=settings.fundamental_cache_ttl_seconds,
            stale_hours=settings.fundamental_valuation_stale_hours,
        )
    except MarketDataError as exc:
        raise market_http_exception(exc) from None
    except FundamentalDataError as exc:
        raise fundamental_http_exception(exc) from None


@router.get(
    "/{stock_id}/valuation/history",
    response_model=ValuationHistoryResponse,
    summary="Valuation snapshot history",
)
def valuation_history(
    stock_id: UUID,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=10000),
    db: Session = Depends(get_db),
    provider: FundamentalDataProvider = Depends(get_fundamental_data_provider),
    cache: FundamentalCache = Depends(get_fundamental_cache),
    _: User = Depends(get_current_user),
) -> ValuationHistoryResponse:
    """Return valuation snapshots in chronological order."""
    if start_date is not None and end_date is not None and start_date > end_date:
        raise HTTPException(status_code=422, detail="start_date must be on or before end_date")
    try:
        return get_valuation_history(
            db,
            stock_id,
            provider=provider,
            cache=cache,
            ttl_seconds=settings.fundamental_cache_ttl_seconds,
            stale_hours=settings.fundamental_valuation_stale_hours,
            start=start_date,
            end=end_date,
            limit=limit,
            offset=offset,
        )
    except MarketDataError as exc:
        raise market_http_exception(exc) from None
    except FundamentalDataError as exc:
        raise fundamental_http_exception(exc) from None


@router.get(
    "/{stock_id}/sector-comparison",
    response_model=SectorComparisonResponse,
    summary="Stock versus stored sector benchmark",
)
def sector_comparison(
    stock_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> SectorComparisonResponse:
    """Return stored stock metrics beside a sector row when one exists. This is not a recommendation."""
    try:
        return get_sector_comparison(db, stock_id)
    except MarketDataError as exc:
        raise market_http_exception(exc) from None


@router.get("/{stock_id}/technical-analysis", response_model=TechnicalAnalysisResponse, summary="Technical analysis")
def technical_analysis(
    stock_id: UUID,
    interval: str = Query(default="1d", max_length=8),
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
    provider: MarketDataProvider = Depends(get_market_data_provider),
    cache: TechnicalCache = Depends(get_technical_cache),
    _: User = Depends(get_current_user),
) -> TechnicalAnalysisResponse:
    """Return indicators, chart patterns, zones, and an evidence-based conclusion."""
    try:
        return get_technical_analysis(
            db,
            stock_id,
            provider=provider,
            cache=cache,
            ttl_seconds=settings.market_data_history_ttl_seconds,
            interval=interval,
            start=start_date,
            end=end_date,
        )
    except MarketDataError as exc:
        raise market_http_exception(exc) from None


@router.get(
    "/{stock_id}/technical-analysis/patterns",
    response_model=PatternHistoryResponse,
    summary="Stored chart patterns",
)
def technical_patterns(
    stock_id: UUID,
    interval: str = Query(default="1d", max_length=8),
    pattern_type: str | None = Query(default=None, max_length=64),
    status: str | None = Query(default=None, max_length=32),
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    provider: MarketDataProvider = Depends(get_market_data_provider),
    cache: TechnicalCache = Depends(get_technical_cache),
    _: User = Depends(get_current_user),
) -> PatternHistoryResponse:
    """Return persisted pattern findings for one listing."""
    try:
        return get_pattern_history(
            db,
            stock_id,
            provider=provider,
            cache=cache,
            ttl_seconds=settings.market_data_history_ttl_seconds,
            interval=interval,
            pattern_type=pattern_type,
            status=status,
            start=start_date,
            end=end_date,
            limit=limit,
            offset=offset,
        )
    except MarketDataError as exc:
        raise market_http_exception(exc) from None


@router.get(
    "/{stock_id}/technical-analysis/summary",
    response_model=TechnicalSummaryResponse,
    summary="Technical conclusion",
)
def technical_summary(
    stock_id: UUID,
    interval: str = Query(default="1d", max_length=8),
    db: Session = Depends(get_db),
    provider: MarketDataProvider = Depends(get_market_data_provider),
    cache: TechnicalCache = Depends(get_technical_cache),
    _: User = Depends(get_current_user),
) -> TechnicalSummaryResponse:
    """Return the latest evidence-based technical conclusion."""
    try:
        return get_technical_summary(
            db,
            stock_id,
            provider=provider,
            cache=cache,
            ttl_seconds=settings.market_data_history_ttl_seconds,
            interval=interval,
        )
    except MarketDataError as exc:
        raise market_http_exception(exc) from None
