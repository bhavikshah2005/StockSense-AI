"""Lexicon sentiment over a headline and a short excerpt.

This is not a price forecast. Mixed or very short text stays uncertain.
No confidence value is stored because the word lists are not calibrated.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

CLASSIFIER_NAME = "lexicon-1"
_TOKENS = re.compile(r"[a-z]{3,}")

POSITIVE = frozenset(
    {
        "profit",
        "profits",
        "growth",
        "rises",
        "rise",
        "rose",
        "gains",
        "gain",
        "beats",
        "beat",
        "upgrade",
        "upgraded",
        "record",
        "strong",
        "surge",
        "surges",
        "approval",
        "approved",
        "wins",
        "win",
        "expands",
        "expansion",
    }
)
NEGATIVE = frozenset(
    {
        "loss",
        "losses",
        "falls",
        "fall",
        "fell",
        "drop",
        "drops",
        "dropped",
        "misses",
        "miss",
        "downgrade",
        "downgraded",
        "weak",
        "fraud",
        "probe",
        "penalty",
        "default",
        "defaults",
        "plunge",
        "plunges",
        "cuts",
        "cut",
        "lawsuit",
    }
)


@dataclass(frozen=True)
class SentimentReading:
    label: str
    score: str
    explanation: str
    input_basis: str


def classify(title: str, summary: str | None) -> SentimentReading:
    basis = "headline_and_excerpt" if summary else "headline"
    tokens = _TOKENS.findall(f"{title} {summary or ''}".lower())
    if len(tokens) < 4:
        return SentimentReading("uncertain", "0", "The text is too short to classify.", basis)
    positive = sorted({token for token in tokens if token in POSITIVE})
    negative = sorted({token for token in tokens if token in NEGATIVE})
    if positive and negative:
        return SentimentReading(
            "uncertain",
            "0",
            f"The text contains both positive words ({', '.join(positive)}) and negative words ({', '.join(negative)}).",
            basis,
        )
    if positive:
        return SentimentReading("positive", "1", f"Matched words: {', '.join(positive)}. This is not a forecast.", basis)
    if negative:
        return SentimentReading("negative", "-1", f"Matched words: {', '.join(negative)}. This is not a forecast.", basis)
    return SentimentReading("neutral", "0", "No listed positive or negative words were found. This is not a forecast.", basis)
