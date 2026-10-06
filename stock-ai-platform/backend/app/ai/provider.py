"""Backend-only model client. The browser never receives the API key."""

from __future__ import annotations

import json
from typing import Protocol

import httpx

from app.ai.explain import SYSTEM_INSTRUCTION
from app.core.config import settings


class AiError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class Explainer(Protocol):
    name: str
    model: str
    configured: bool

    def explain(self, evidence: dict[str, object]) -> dict[str, object]:
        """Return a JSON object for schema validation."""


class UnconfiguredExplainer:
    name = "unconfigured"
    model = "none"
    configured = False

    def explain(self, evidence: dict[str, object]) -> dict[str, object]:
        del evidence
        raise AiError("ai_unavailable")


class OpenAiCompatibleExplainer:
    """Chat-completions client. Tests pass a fake transport."""

    def __init__(self, *, api_key: str, model: str, base_url: str, timeout: float, max_tokens: int, transport: httpx.BaseTransport | None = None) -> None:
        self.name = "openai"
        self.model = model
        self.configured = True
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._max_tokens = max_tokens
        self._transport = transport

    def explain(self, evidence: dict[str, object]) -> dict[str, object]:
        payload = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": self._max_tokens,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": SYSTEM_INSTRUCTION},
                {"role": "user", "content": json.dumps(evidence, default=str)},
            ],
        }
        try:
            with httpx.Client(timeout=self._timeout, transport=self._transport) as client:
                response = client.post(
                    f"{self._base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json=payload,
                )
        except httpx.TimeoutException as exc:
            raise AiError("timeout") from exc
        except httpx.HTTPError as exc:
            raise AiError("unavailable") from exc
        if response.status_code == 429:
            raise AiError("rate_limited")
        if response.status_code >= 400:
            raise AiError("unavailable")
        try:
            body = response.json()
            content = body["choices"][0]["message"]["content"]
            parsed = json.loads(content)
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise AiError("malformed") from exc
        if not isinstance(parsed, dict):
            raise AiError("malformed")
        return parsed


def get_explainer() -> Explainer:
    provider = settings.ai_provider.strip().lower()
    if provider == "openai" and settings.ai_api_key.strip() and settings.ai_model.strip():
        return OpenAiCompatibleExplainer(
            api_key=settings.ai_api_key,
            model=settings.ai_model,
            base_url=settings.ai_base_url,
            timeout=float(settings.ai_timeout_seconds),
            max_tokens=settings.ai_max_output_tokens,
        )
    return UnconfiguredExplainer()
