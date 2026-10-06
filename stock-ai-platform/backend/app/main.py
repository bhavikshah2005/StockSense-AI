import logging
import uuid

from fastapi import FastAPI, Request, Response
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis.exceptions import RedisError
from sqlalchemy import text

from app.api.routes import ai, alerts, auth, backtests, markets, metrics, news, portfolio, stocks, users, watchlist
from app.core.config import settings
from app.core.database import engine
from app.core.origin import OriginCheckMiddleware
from app.core.redis import get_redis
from app.schemas.health import HealthResponse, LiveResponse, ReadyResponse

logger = logging.getLogger(__name__)

_production = settings.app_env == "production"
app = FastAPI(
    title="StockSense AI",
    version="0.1.0",
    docs_url=None if _production else "/docs",
    redoc_url=None if _production else "/redoc",
    openapi_url=None if _production else "/openapi.json",
)

app.add_middleware(OriginCheckMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Accept", "Content-Type", "X-Request-ID"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    request.state.request_id = request_id
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("request failed request_id=%s path=%s", request_id, request.url.path)
        response = JSONResponse(status_code=500, content={"detail": "Something went wrong. Try again."})
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if _production:
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    logger.info("request method=%s path=%s status=%s request_id=%s", request.method, request.url.path, response.status_code, request_id)
    return response


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception) -> Response:
    if isinstance(exc, HTTPException):
        return await http_exception_handler(request, exc)
    if isinstance(exc, RequestValidationError):
        return await request_validation_exception_handler(request, exc)
    request_id = getattr(request.state, "request_id", "")
    logger.exception("unhandled error request_id=%s path=%s", request_id, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Something went wrong. Try again."})

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(stocks.router)
app.include_router(markets.router)
app.include_router(watchlist.router)
app.include_router(metrics.router)
app.include_router(alerts.router)
app.include_router(alerts.notifications)
app.include_router(news.router)
app.include_router(portfolio.router)
app.include_router(ai.router)
app.include_router(backtests.router)


def _database_ok() -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        logger.warning("database readiness check failed")
        return False
    return True


def _redis_ok() -> bool:
    try:
        get_redis().ping()
    except RedisError:
        return False
    return True


@app.get("/live", response_model=LiveResponse)
def live() -> LiveResponse:
    """Process liveness. This does not check dependencies."""
    return LiveResponse(status="ok")


@app.get("/ready", response_model=ReadyResponse)
def ready(response: Response) -> ReadyResponse:
    """Readiness. PostgreSQL is required. Redis is reported and is not required."""
    database_ok = _database_ok()
    if not database_ok:
        response.status_code = 503
    return ReadyResponse(
        status="ok" if database_ok else "unavailable",
        database="ok" if database_ok else "unavailable",
        redis="ok" if _redis_ok() else "unavailable",
    )


@app.get("/health", response_model=HealthResponse)
def health(response: Response) -> HealthResponse:
    if not _database_ok():
        response.status_code = 503
        return HealthResponse(status="degraded", database="unavailable")
    return HealthResponse(status="ok", database="ok")
