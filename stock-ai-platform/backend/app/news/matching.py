"""Link headlines to the stock master.

A symbol match requires an uppercase token of at least three characters.
A company match uses the distinctive part of the legal name and prefers the
longest phrase so "Reliance Power" does not also attach to "Reliance".
Ambiguous phrases are left unlinked.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import UUID

_SUFFIX = re.compile(r"\b(limited|ltd|pvt|private|inc|incorporated|corp|corporation|plc|company|co)\b\.?", re.IGNORECASE)
_TOKEN = re.compile(r"\b[A-Z][A-Z0-9&.-]{2,15}\b")
_STOP = frozenset(
    {
        "and",
        "the",
        "of",
        "india",
        "indian",
        "industries",
        "industry",
        "services",
        "service",
        "technology",
        "technologies",
        "bank",
        "banks",
        "finance",
        "financial",
        "capital",
        "group",
        "holdings",
        "international",
        "global",
        "national",
        "systems",
        "solutions",
        "enterprises",
        "enterprise",
        "corporation",
        "limited",
    }
)
_SYMBOL_DENY = frozenset({"ALL", "ARE", "FOR", "THE", "AND", "NOT", "BUT", "CAN", "NOW", "BIG", "NEW", "OLD", "IT"})


@dataclass(frozen=True)
class StockName:
    id: UUID
    symbol: str
    company_name: str


@dataclass(frozen=True)
class StockMatch:
    stock_id: UUID
    method: str
    quality: str


def distinctive_name(company: str) -> str | None:
    cleaned = _SUFFIX.sub(" ", company.lower())
    cleaned = re.sub(r"[^a-z0-9\s]", " ", cleaned)
    tokens = [token for token in cleaned.split() if token not in _STOP and len(token) > 2]
    if not tokens:
        return None
    if len(tokens) == 1 and len(tokens[0]) < 6:
        return None
    phrase = " ".join(tokens)
    if len(phrase) < 6:
        return None
    return phrase


def match_stocks(title: str, summary: str | None, stocks: list[StockName]) -> list[StockMatch]:
    text = f"{title}\n{summary or ''}"
    lowered = text.lower()
    matches: list[StockMatch] = []
    seen: set[UUID] = set()

    symbols = {stock.symbol.upper() for stock in stocks if len(stock.symbol) >= 3 and stock.symbol.upper() not in _SYMBOL_DENY}
    found_symbols = {token for token in _TOKEN.findall(text) if token in symbols}
    for stock in stocks:
        if stock.symbol.upper() in found_symbols and stock.id not in seen:
            seen.add(stock.id)
            matches.append(StockMatch(stock.id, "symbol", "confirmed"))

    phrases: dict[str, list[UUID]] = {}
    for stock in stocks:
        phrase = distinctive_name(stock.company_name)
        if phrase:
            phrases.setdefault(phrase, []).append(stock.id)
    occupied: list[tuple[int, int]] = []
    for phrase in sorted(phrases, key=len, reverse=True):
        pattern = re.compile(rf"\b{re.escape(phrase)}\b")
        for found in pattern.finditer(lowered):
            span = found.span()
            if any(span[0] < end and span[1] > start for start, end in occupied):
                continue
            occupied.append(span)
            for stock_id in phrases[phrase]:
                if stock_id not in seen:
                    seen.add(stock_id)
                    matches.append(StockMatch(stock_id, "company_name", "confirmed"))
            break
    return matches
