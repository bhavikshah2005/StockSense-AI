class NewsProviderError(Exception):
    """A provider failed. `code` is timeout, rate_limited, malformed, or unavailable."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)
