from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.metrics.service import (
    DUPLICATE,
    INVALID_CONDITION,
    MESSAGES,
    NOT_FOUND,
    STOCK_NOT_FOUND,
    TOO_MANY,
    UNKNOWN_METRIC,
    ThresholdError,
    create_user_threshold,
    delete_user_threshold,
    evaluate_stock,
    list_registry,
    list_thresholds,
    update_user_threshold,
)
from app.models import User
from app.models.metric_threshold import MetricThreshold
from app.schemas.metrics import (
    EvaluationRequest,
    EvaluationResponse,
    MetricRegistryResponse,
    ThresholdListResponse,
    ThresholdResponse,
    ThresholdUpdate,
    ThresholdWrite,
)

router = APIRouter(prefix="/api/metrics", tags=["metrics"])

_STATUS = {
    NOT_FOUND: 404,
    STOCK_NOT_FOUND: 404,
    UNKNOWN_METRIC: 422,
    INVALID_CONDITION: 422,
    DUPLICATE: 409,
    TOO_MANY: 422,
}


def _raise(exc: ThresholdError) -> HTTPException:
    return HTTPException(status_code=_STATUS.get(exc.code, 422), detail=MESSAGES[exc.code])


def _public(row: MetricThreshold, user: User) -> ThresholdResponse:
    operator = row.operator.value if hasattr(row.operator, "value") else str(row.operator)
    scope = row.scope.value if hasattr(row.scope, "value") else str(row.scope)
    return ThresholdResponse(
        id=row.id,
        metric_key=row.metric_name,
        scope=scope,
        country=row.country,
        sector=row.sector,
        stock_id=row.stock_id,
        operator=operator,
        basis=row.basis,
        threshold_value=format(row.threshold_value, "f") if row.threshold_value is not None else None,
        threshold_high=format(row.threshold_high, "f") if row.threshold_high is not None else None,
        description=row.description,
        is_active=row.is_active,
        effective_from=row.effective_from,
        effective_to=row.effective_to,
        definition_version=row.definition_version,
        owned=row.user_id == user.id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("/registry", response_model=MetricRegistryResponse, summary="Supported metrics")
def registry(user: User = Depends(get_current_user)) -> dict[str, object]:
    """Return the metric registry. Authentication is required. Definitions are not user-specific."""
    del user
    return list_registry()


@router.get("/thresholds", response_model=ThresholdListResponse, summary="Applicable thresholds")
def thresholds(
    metric_key: str | None = None,
    stock_id: UUID | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ThresholdListResponse:
    """Return platform, market, and sector defaults plus the signed-in user's thresholds."""
    try:
        rows = list_thresholds(db, user, metric_key=metric_key, stock_id=stock_id)
    except ThresholdError as exc:
        raise _raise(exc) from None
    return ThresholdListResponse(results=[_public(row, user) for row in rows])


@router.post("/thresholds", response_model=ThresholdResponse, status_code=201, summary="Create a personal threshold")
def create(
    payload: ThresholdWrite,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ThresholdResponse:
    """Create a threshold owned by the signed-in user. Global defaults stay read-only."""
    try:
        row = create_user_threshold(db, user, payload.model_dump())
    except ThresholdError as exc:
        raise _raise(exc) from None
    return _public(row, user)


@router.patch("/thresholds/{threshold_id}", response_model=ThresholdResponse, summary="Update a personal threshold")
def update(
    threshold_id: UUID,
    payload: ThresholdUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ThresholdResponse:
    """Change a threshold owned by the signed-in user."""
    try:
        row = update_user_threshold(db, user, threshold_id, payload.model_dump(exclude_unset=True))
    except ThresholdError as exc:
        raise _raise(exc) from None
    return _public(row, user)


@router.delete("/thresholds/{threshold_id}", status_code=204, summary="Delete a personal threshold")
def delete(
    threshold_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    """Delete a threshold owned by the signed-in user."""
    try:
        delete_user_threshold(db, user, threshold_id)
    except ThresholdError as exc:
        raise _raise(exc) from None
    return Response(status_code=204)


@router.post("/evaluate", response_model=EvaluationResponse, summary="Evaluate thresholds for one stock")
def evaluate(
    payload: EvaluationRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> EvaluationResponse:
    """Resolve and evaluate thresholds. Missing data stays missing. This does not create an alert."""
    try:
        body = evaluate_stock(db, user, payload.stock_id, payload.metric_keys)
    except ThresholdError as exc:
        raise _raise(exc) from None
    return EvaluationResponse.model_validate(body)
