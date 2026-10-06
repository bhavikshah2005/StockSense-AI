"""Errors raised by market-data providers and the market-data service.

Public HTTP text is chosen by the API layer from `code`. Provider exceptions
must not include credentials, and their messages are not returned to clients.
"""

NOT_CONFIGURED = "not_configured"
TIMEOUT = "timeout"
UNAVAILABLE = "unavailable"
UNAUTHORIZED = "unauthorized"
RATE_LIMITED = "rate_limited"
MALFORMED = "malformed"
NOT_FOUND = "not_found"
UNSUPPORTED_EXCHANGE = "unsupported_exchange"
UNSUPPORTED_INTERVAL = "unsupported_interval"
INVALID_RANGE = "invalid_range"
INVALID_QUERY = "invalid_query"

HTTP_STATUS: dict[str, int] = {
    NOT_CONFIGURED: 503,
    TIMEOUT: 502,
    UNAVAILABLE: 502,
    UNAUTHORIZED: 502,
    RATE_LIMITED: 429,
    MALFORMED: 502,
    NOT_FOUND: 404,
    UNSUPPORTED_EXCHANGE: 422,
    UNSUPPORTED_INTERVAL: 422,
    INVALID_RANGE: 422,
    INVALID_QUERY: 422,
}

PUBLIC_MESSAGE: dict[str, str] = {
    NOT_CONFIGURED: "Market data service temporarily unavailable",
    TIMEOUT: "Market data provider unavailable",
    UNAVAILABLE: "Market data provider unavailable",
    UNAUTHORIZED: "Market data provider unavailable",
    RATE_LIMITED: "Market data rate limit reached",
    MALFORMED: "Market data provider unavailable",
    NOT_FOUND: "Stock not found",
    UNSUPPORTED_EXCHANGE: "Exchange is not supported",
    UNSUPPORTED_INTERVAL: "Interval is not supported",
    INVALID_RANGE: "A start date is required for the first historical sync",
    INVALID_QUERY: "The requested date range is invalid",
}


class MarketDataError(Exception):
    def __init__(self, code: str) -> None:
        if code not in PUBLIC_MESSAGE:
            code = NOT_CONFIGURED
        self.code = code
        super().__init__(PUBLIC_MESSAGE[code])
