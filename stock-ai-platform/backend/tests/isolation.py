"""Hide committed market rows inside a test transaction.

The savepoint rollback in conftest restores them. Tests can then insert
their own bars and statements without colliding with a live sync.
"""

from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models import Fundamental, StockPrice, TechnicalIndicator, TechnicalPattern, ValuationSnapshot


def hide_committed_market_rows(db: Session, stock_id: UUID) -> None:
    db.execute(delete(TechnicalPattern).where(TechnicalPattern.stock_id == stock_id))
    db.execute(delete(TechnicalIndicator).where(TechnicalIndicator.stock_id == stock_id))
    db.execute(delete(StockPrice).where(StockPrice.stock_id == stock_id))
    db.execute(delete(Fundamental).where(Fundamental.stock_id == stock_id))
    db.execute(delete(ValuationSnapshot).where(ValuationSnapshot.stock_id == stock_id))
    db.flush()
