from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ResearchResponse(BaseModel):
    id: UUID
    stock_id: UUID
    symbol: str
    exchange: str
    status: str
    analysis_timestamp: datetime
    evidence: dict[str, Any]
    explanation: dict[str, Any] | None
    score: dict[str, Any]
    provider: str
    model_name: str
    prompt_version: str
    scoring_version: str
    error_message: str | None
    created_at: datetime


class ResearchListResponse(BaseModel):
    results: list[ResearchResponse]
    total: int
    limit: int
    offset: int


class MethodologyResponse(BaseModel):
    prompt_version: str
    scoring_version: str
    scoring_note: str
    ai_note: str
    configured: bool
    provider: str


class ResearchQuery(BaseModel):
    limit: int = Field(default=20, ge=1, le=50)
    offset: int = Field(default=0, ge=0)
