"""Compact evidence from existing service results. This module does not recalculate metrics."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any


def pack_evidence(
    *,
    stock_id: str,
    symbol: str,
    exchange: str,
    fundamental: list[dict[str, Any]],
    technical: dict[str, Any] | None,
    patterns: list[dict[str, Any]],
    news: list[dict[str, Any]],
    gaps: list[str],
    as_of: datetime | None = None,
) -> dict[str, Any]:
    moment = as_of or datetime.now(UTC)
    body = {
        "stock_id": stock_id,
        "symbol": symbol,
        "exchange": exchange,
        "fundamental": fundamental,
        "technical": technical,
        "patterns": patterns,
        "news": news,
        "gaps": gaps,
    }
    digest = hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    return {**body, "assembled_at": moment.isoformat(), "input_hash": digest}
