from fastapi import HTTPException

from app.data_providers.market_data.errors import HTTP_STATUS, PUBLIC_MESSAGE, MarketDataError


def market_http_exception(exc: MarketDataError) -> HTTPException:
    status = HTTP_STATUS.get(exc.code, 503)
    detail = PUBLIC_MESSAGE.get(exc.code, PUBLIC_MESSAGE["not_configured"])
    return HTTPException(status_code=status, detail=detail)
