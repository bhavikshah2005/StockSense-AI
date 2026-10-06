"""Threshold API models. Values are decimal strings. A result is not a trade instruction."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class MetricDefinitionResponse(BaseModel):
    key: str
    name: str
    description: str
    category: str
    unit: str
    operators: list[str]
    source: str
    preference: str
    sector_benchmark: bool
    event_kind: str | None


class MetricRegistryResponse(BaseModel):
    version: str
    metrics: list[MetricDefinitionResponse]


class ThresholdWrite(BaseModel):
    metric_key: str = Field(min_length=1, max_length=64)
    operator: str
    basis: str = "absolute"
    threshold_value: str | None = None
    threshold_high: str | None = None
    description: str | None = Field(default=None, max_length=500)
    stock_id: UUID | None = None
    effective_from: date | None = None
    effective_to: date | None = None


class ThresholdUpdate(BaseModel):
    operator: str | None = None
    basis: str | None = None
    threshold_value: str | None = None
    threshold_high: str | None = None
    description: str | None = Field(default=None, max_length=500)
    stock_id: UUID | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    is_active: bool | None = None


class ThresholdResponse(BaseModel):
    id: UUID
    metric_key: str
    scope: str
    country: str | None
    sector: str | None
    stock_id: UUID | None
    operator: str
    basis: str
    threshold_value: str | None
    threshold_high: str | None
    description: str | None
    is_active: bool
    effective_from: date | None
    effective_to: date | None
    definition_version: str
    owned: bool
    created_at: datetime
    updated_at: datetime


class ThresholdListResponse(BaseModel):
    results: list[ThresholdResponse]


class ResolvedThresholdResponse(BaseModel):
    id: str
    scope: str
    operator: str
    basis: str
    threshold_value: str | None
    threshold_high: str | None
    definition_version: str
    effective_from: str | None
    reason: str
    skipped_scopes: list[str]
    user_override: bool


class MetricEvaluationResponse(BaseModel):
    metric_key: str
    metric_name: str
    category: str
    unit: str
    state: str
    explanation: str
    value: str | None
    previous_value: str | None
    reference_value: str | None
    as_of: datetime | None
    source: str | None
    threshold: ResolvedThresholdResponse | None


class EvaluationRequest(BaseModel):
    stock_id: UUID
    metric_keys: list[str] | None = None


class EvaluationResponse(BaseModel):
    stock_id: UUID
    registry_version: str
    evaluated_at: datetime
    results: list[MetricEvaluationResponse]
