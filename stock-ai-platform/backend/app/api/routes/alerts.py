from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.alerts.catalog import catalog_payload
from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import Alert, AlertEvent, Notification, User
from app.schemas.alerts import (
    AlertEventListResponse,
    AlertEventResponse,
    AlertListResponse,
    AlertPreviewResponse,
    AlertResponse,
    AlertUpdate,
    AlertWrite,
    NotificationListResponse,
    NotificationResponse,
    PreferenceResponse,
    PreferenceUpdate,
)
from app.services.alert_service import (
    INVALID,
    MESSAGES,
    NOT_FOUND,
    STOCK_NOT_FOUND,
    TOO_MANY,
    AlertError,
    create_alert,
    delete_alert,
    get_alert,
    get_preferences,
    list_alerts,
    list_events,
    list_notifications,
    mark_all_read,
    mark_read,
    pause_alert,
    preview_alert,
    resume_alert,
    unread_count,
    update_alert,
    update_preferences,
)

router = APIRouter(prefix="/api/alerts", tags=["alerts"])
notifications = APIRouter(prefix="/api/notifications", tags=["notifications"])

_STATUS = {NOT_FOUND: 404, STOCK_NOT_FOUND: 404, INVALID: 422, TOO_MANY: 422}


def _raise(exc: AlertError) -> HTTPException:
    return HTTPException(status_code=_STATUS.get(exc.code, 422), detail=MESSAGES[exc.code])


def _decimal(value: object) -> str | None:
    if value is None:
        return None
    return format(value, "f")


def _alert(row: Alert) -> AlertResponse:
    operator = row.operator.value if hasattr(row.operator, "value") else str(row.operator)
    threshold_type = row.threshold_type.value if hasattr(row.threshold_type, "value") else str(row.threshold_type)
    return AlertResponse(
        id=row.id,
        stock_id=row.stock_id,
        symbol=row.stock.symbol,
        exchange=row.stock.exchange,
        company_name=row.stock.company_name,
        category=row.category,
        metric=row.metric,
        operator=operator,
        threshold_type=threshold_type,
        threshold_value=_decimal(row.threshold_value),
        threshold_high=_decimal(row.threshold_high),
        pattern_type=row.pattern_type,
        pattern_status=row.pattern_status,
        percent_interval=row.percent_interval,
        repeat_mode=row.repeat_mode,
        status=row.status,
        armed=row.armed,
        note=row.note,
        last_evaluated_at=row.last_evaluated_at,
        last_data_status=row.last_data_status,
        last_value=_decimal(row.last_value),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _event(row: AlertEvent) -> AlertEventResponse:
    return AlertEventResponse(
        id=row.id,
        alert_id=row.alert_id,
        stock_id=row.stock_id,
        triggered_value=_decimal(row.triggered_value) or "0",
        previous_value=_decimal(row.previous_value),
        threshold_value=_decimal(row.threshold_value) or "0",
        triggered_at=row.triggered_at,
        observed_at=row.observed_at,
        message=row.message,
        data_status=row.data_status,
        source=row.source,
    )


def _notification(row: Notification) -> NotificationResponse:
    event = row.event
    return NotificationResponse(
        id=row.id,
        alert_id=event.alert_id,
        stock_id=event.stock_id,
        symbol=event.stock.symbol,
        message=event.message,
        triggered_at=event.triggered_at,
        read_at=row.read_at,
        created_at=row.created_at,
    )


@router.get("/catalog", summary="Supported alert conditions")
def catalog(user: User = Depends(get_current_user)) -> dict[str, object]:
    del user
    return catalog_payload()


@router.get("", response_model=AlertListResponse, summary="List the current user's alerts")
def alerts(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AlertListResponse:
    rows, total = list_alerts(db, user, limit=limit, offset=offset)
    return AlertListResponse(results=[_alert(row) for row in rows], total=total, limit=limit, offset=offset)


@router.post("", response_model=AlertResponse, status_code=201, summary="Create an alert")
def create(
    payload: AlertWrite,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AlertResponse:
    try:
        row = create_alert(db, user, payload.model_dump())
    except AlertError as exc:
        raise _raise(exc) from None
    return _alert(row)


@router.get("/{alert_id}", response_model=AlertResponse, summary="Read one owned alert")
def read_alert(
    alert_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AlertResponse:
    try:
        return _alert(get_alert(db, user, alert_id))
    except AlertError as exc:
        raise _raise(exc) from None


@router.patch("/{alert_id}", response_model=AlertResponse, summary="Update an owned alert")
def update(
    alert_id: UUID,
    payload: AlertUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AlertResponse:
    try:
        row = update_alert(db, user, alert_id, payload.model_dump(exclude_unset=True))
    except AlertError as exc:
        raise _raise(exc) from None
    return _alert(row)


@router.delete("/{alert_id}", status_code=204, summary="Delete an owned alert")
def remove(
    alert_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    try:
        delete_alert(db, user, alert_id)
    except AlertError as exc:
        raise _raise(exc) from None
    return Response(status_code=204)


@router.post("/{alert_id}/pause", response_model=AlertResponse, summary="Pause an active alert")
def pause(
    alert_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AlertResponse:
    try:
        return _alert(pause_alert(db, user, alert_id))
    except AlertError as exc:
        raise _raise(exc) from None


@router.post("/{alert_id}/resume", response_model=AlertResponse, summary="Resume a paused or triggered alert")
def resume(
    alert_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AlertResponse:
    try:
        return _alert(resume_alert(db, user, alert_id))
    except AlertError as exc:
        raise _raise(exc) from None


@router.get("/{alert_id}/events", response_model=AlertEventListResponse, summary="Trigger history for an owned alert")
def events(
    alert_id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AlertEventListResponse:
    try:
        rows, total = list_events(db, user, alert_id, limit=limit, offset=offset)
    except AlertError as exc:
        raise _raise(exc) from None
    return AlertEventListResponse(results=[_event(row) for row in rows], total=total, limit=limit, offset=offset)


@router.post("/{alert_id}/preview", response_model=AlertPreviewResponse, summary="Preview the current evaluation without triggering")
def preview(
    alert_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    try:
        return preview_alert(db, user, alert_id)
    except AlertError as exc:
        raise _raise(exc) from None


@notifications.get("", response_model=NotificationListResponse, summary="In-app notifications")
def inbox(
    unread: bool | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NotificationListResponse:
    rows, total = list_notifications(db, user, unread=unread, limit=limit, offset=offset)
    return NotificationListResponse(
        results=[_notification(row) for row in rows],
        total=total,
        unread=unread_count(db, user),
        limit=limit,
        offset=offset,
    )


@notifications.post("/read", summary="Mark every unread notification as read")
def read_all(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, int]:
    return {"updated": mark_all_read(db, user)}


@notifications.post("/{notification_id}/read", response_model=NotificationResponse, summary="Mark one notification as read")
def read_one(
    notification_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NotificationResponse:
    try:
        return _notification(mark_read(db, user, notification_id))
    except AlertError as exc:
        raise _raise(exc) from None


@notifications.get("/preferences", response_model=PreferenceResponse, summary="Notification preferences")
def preferences(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> PreferenceResponse:
    row = get_preferences(db, user)
    return PreferenceResponse(in_app_enabled=row.in_app_enabled)


@notifications.patch("/preferences", response_model=PreferenceResponse, summary="Update notification preferences")
def update_preference(
    payload: PreferenceUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PreferenceResponse:
    try:
        row = update_preferences(db, user, payload.model_dump(exclude_unset=True))
    except AlertError as exc:
        raise _raise(exc) from None
    return PreferenceResponse(in_app_enabled=row.in_app_enabled)
