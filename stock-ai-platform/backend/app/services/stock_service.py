from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.markets.profile import MarketProfile, active_market
from app.models import Stock
from app.schemas.stock import StockSearchResponse, StockSearchResult

_MAX_RESULTS = 20


def search_stocks(db: Session, query: str, market: MarketProfile | None = None) -> StockSearchResponse:
    """Search the active market's listings. The query is not a user id and is not trusted as one."""
    profile = market or active_market()
    term = query.strip()
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    pattern = f"%{escaped}%"
    prefix = f"{escaped}%"
    symbol_match = Stock.symbol.ilike(prefix, escape="\\")
    rows = db.scalars(
        select(Stock)
        .where(
            Stock.country == profile.country,
            Stock.exchange.in_(profile.exchanges),
            Stock.is_active.is_(True),
            or_(
                Stock.symbol.ilike(pattern, escape="\\"),
                Stock.company_name.ilike(pattern, escape="\\"),
                Stock.isin.ilike(pattern, escape="\\"),
            ),
        )
        .order_by(symbol_match.desc(), Stock.symbol, Stock.exchange)
        .limit(_MAX_RESULTS)
    ).all()
    return StockSearchResponse(
        query=term,
        results=[
            StockSearchResult(
                id=row.id,
                symbol=row.symbol,
                company_name=row.company_name,
                exchange=row.exchange,
                sector=row.sector,
                industry=row.industry,
                currency=row.currency,
                country=row.country,
                country_name=profile.country_name,
                isin=row.isin,
            )
            for row in rows
        ],
    )
