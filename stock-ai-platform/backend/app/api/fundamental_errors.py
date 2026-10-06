from fastapi import HTTPException

from app.data_providers.fundamentals.errors import HTTP_STATUS, PUBLIC_MESSAGE, FundamentalDataError


def fundamental_http_exception(exc: FundamentalDataError) -> HTTPException:
    status = HTTP_STATUS.get(exc.code, 503)
    detail = PUBLIC_MESSAGE.get(exc.code, PUBLIC_MESSAGE["not_configured"])
    return HTTPException(status_code=status, detail=detail)
