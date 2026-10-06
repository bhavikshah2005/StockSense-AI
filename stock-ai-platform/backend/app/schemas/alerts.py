from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AlertWrite(BaseModel):
    stock_id: UUID
    category: str
    metric: str
    operator: str
    threshold_type: str
    threshold_value: str | None = None
    threshold_high: str | None = None
    pattern_type: str | None = None
    pattern_status: str | None = None
    percent_interval: str | None = None
    repeat_mode: str = "once"
    note: str | None = None


class AlertUpdate(BaseModel):
    stock_id: UUID | None = None
    category: str | None = None
    metric: str | None = None
    operator: str | None = None
    threshold_type: str | None = None
    threshold_value: str | None = None
    threshold_high: str | None = None
    pattern_type: str | None = None
    pattern_status: str | None = None
    percent_interval: str | None = None
    repeat_mode: str | None = None
    note: str | None = None


class AlertResponse(BaseModel):
    id: UUID
    stock_id: UUID
    symbol: str
    exchange: str
    company_name: str
    category: str
    metric: str
    operator: str
    threshold_type: str
    threshold_value: str | None
    threshold_high: str | None
    pattern_type: str | None
    pattern_status: str | None
    percent_interval: str | None
    repeat_mode: str
    status: str
    armed: bool
    note: str | None
    last_evaluated_at: datetime | None
    last_data_status: str | None
    last_value: str | None
    created_at: datetime
    updated_at: datetime


class AlertListResponse(BaseModel):
    results: list[AlertResponse]
    total: int
    limit: int
    offset: int


class AlertEventResponse(BaseModel):
    id: UUID
    alert_id: UUID
    stock_id: UUID
    triggered_value: str
    previous_value: str | None
    threshold_value: str
    triggered_at: datetime
    observed_at: datetime | None
    message: str
    data_status: str
    source: str | None


class AlertEventListResponse(BaseModel):
    results: list[AlertEventResponse]
    total: int
    limit: int
    offset: int


class AlertPreviewResponse(BaseModel):
    alert_id: UUID
    preview: bool
    state: str
    explanation: str
    value: str | None
    previous_value: str | None
    reference_value: str | None
    observed_at: datetime | None
    source: str | None
    would_trigger: bool


class NotificationResponse(BaseModel):
    id: UUID
    alert_id: UUID
    stock_id: UUID
    symbol: str
    message: str
    triggered_at: datetime
    read_at: datetime | None
    created_at: datetime


class NotificationListResponse(BaseModel):
    results: list[NotificationResponse]
    total: int
    unread: int
    limit: int
    offset: int


class PreferenceResponse(BaseModel):
    in_app_enabled: bool


class PreferenceUpdate(BaseModel):
    in_app_enabled: bool | None = None


class PageQuery(BaseModel):
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
