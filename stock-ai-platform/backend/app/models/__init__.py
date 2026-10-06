"""ORM models. Importing this package registers every table on Base.metadata."""

from app.core.database import Base
from app.models.ai_analysis import AiAnalysis
from app.models.alert import Alert, AlertEvent, Notification, NotificationPreference
from app.models.backtest import BacktestEquityPoint, BacktestRun, BacktestTrade
from app.models.fundamental import Fundamental
from app.models.metric_threshold import MetricThreshold
from app.models.news import NewsArticle, NewsArticleStock, NewsIngestRun, NewsSentiment
from app.models.password_reset import PasswordResetToken
from app.models.portfolio import Portfolio, PortfolioCashMovement, PortfolioHolding, PortfolioTransaction, UserRiskSettings
from app.models.price import StockPrice
from app.models.research import ResearchAnalysis
from app.models.sector_benchmark import SectorBenchmark
from app.models.session import UserSession
from app.models.stock import Stock
from app.models.technical import TechnicalIndicator, TechnicalPattern
from app.models.user import User
from app.models.valuation import ValuationSnapshot
from app.models.watchlist import Watchlist, WatchlistStock

__all__ = [
    "AiAnalysis",
    "Alert",
    "AlertEvent",
    "BacktestEquityPoint",
    "BacktestRun",
    "BacktestTrade",
    "Notification",
    "NotificationPreference",
    "Base",
    "Fundamental",
    "MetricThreshold",
    "NewsArticle",
    "NewsArticleStock",
    "NewsIngestRun",
    "NewsSentiment",
    "PasswordResetToken",
    "Portfolio",
    "PortfolioCashMovement",
    "PortfolioHolding",
    "PortfolioTransaction",
    "UserRiskSettings",
    "ResearchAnalysis",
    "SectorBenchmark",
    "Stock",
    "StockPrice",
    "TechnicalIndicator",
    "TechnicalPattern",
    "User",
    "UserSession",
    "ValuationSnapshot",
    "Watchlist",
    "WatchlistStock",
]
