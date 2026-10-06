"""Fundamental-data errors. HTTP text comes from the code, not the provider body."""

NOT_CONFIGURED = "not_configured"
TIMEOUT = "timeout"
UNAVAILABLE = "unavailable"
UNAUTHORIZED = "unauthorized"
RATE_LIMITED = "rate_limited"
MALFORMED = "malformed"
NOT_FOUND = "not_found"
UNSUPPORTED_EXCHANGE = "unsupported_exchange"

HTTP_STATUS: dict[str, int] = {
    NOT_CONFIGURED: 503,
    TIMEOUT: 502,
    UNAVAILABLE: 502,
    UNAUTHORIZED: 502,
    RATE_LIMITED: 429,
    MALFORMED: 502,
    NOT_FOUND: 404,
    UNSUPPORTED_EXCHANGE: 422,
}

PUBLIC_MESSAGE: dict[str, str] = {
    NOT_CONFIGURED: "Fundamental data provider is not configured",
    TIMEOUT: "Fundamental data provider unavailable",
    UNAVAILABLE: "Fundamental data provider unavailable",
    UNAUTHORIZED: "Fundamental data provider unavailable",
    RATE_LIMITED: "Fundamental data rate limit reached",
    MALFORMED: "Fundamental data provider unavailable",
    NOT_FOUND: "Stock not found",
    UNSUPPORTED_EXCHANGE: "Exchange is not supported",
}


class FundamentalDataError(Exception):
    def __init__(self, code: str) -> None:
        if code not in PUBLIC_MESSAGE:
            code = NOT_CONFIGURED
        self.code = code
        super().__init__(PUBLIC_MESSAGE[code])
