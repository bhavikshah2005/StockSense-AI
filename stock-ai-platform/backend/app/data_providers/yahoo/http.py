"""HTTP access for the public Yahoo Finance chart and fundamentals feeds.

No API key is required. Responses are not logged. Callers map status codes
onto the market-data or fundamental error types.
"""

from typing import Any

import httpx

DEFAULT_BASE_URL = "https://query1.finance.yahoo.com"
_USER_AGENT = "StockSenseAI/1.0"


class YahooStatus(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class YahooClient:
    def __init__(self, base_url: str = DEFAULT_BASE_URL, transport: httpx.BaseTransport | None = None) -> None:
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=20.0,
            headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
            transport=transport,
        )

    def get_json(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        try:
            response = self._client.get(path, params=params)
        except httpx.TimeoutException as exc:
            raise TimeoutError from exc
        except httpx.HTTPError as exc:
            raise OSError("yahoo request failed") from exc
        if response.status_code == 429:
            raise YahooStatus("rate_limited")
        if response.status_code in {401, 403}:
            raise YahooStatus("unauthorized")
        if response.status_code == 404:
            raise YahooStatus("not_found")
        if response.status_code >= 400:
            raise YahooStatus("unavailable")
        try:
            body = response.json()
        except ValueError as exc:
            raise YahooStatus("malformed") from exc
        if not isinstance(body, dict):
            raise YahooStatus("malformed")
        return body

    def close(self) -> None:
        self._client.close()
