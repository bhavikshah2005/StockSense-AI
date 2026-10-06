from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.ai.provider import get_explainer
from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.rate_limit import RateLimiter, get_rate_limiter
from app.models import ResearchAnalysis, User
from app.schemas.research import MethodologyResponse, ResearchListResponse, ResearchResponse
from app.services.ai_service import METHODOLOGY, ResearchError, get_analysis, latest_analysis, list_analyses, request_analysis

router = APIRouter(prefix="/api/ai", tags=["ai"])

_STATUS = {"not_found": 404, "quota": 429}


def _response(row: ResearchAnalysis) -> ResearchResponse:
    return ResearchResponse(
        id=row.id,
        stock_id=row.stock_id,
        symbol=row.stock.symbol,
        exchange=row.stock.exchange,
        status=row.status,
        analysis_timestamp=row.analysis_timestamp,
        evidence=row.evidence,
        explanation=row.explanation,
        score=row.score,
        provider=row.provider,
        model_name=row.model_name,
        prompt_version=row.prompt_version,
        scoring_version=row.scoring_version,
        error_message=row.error_message,
        created_at=row.created_at,
    )


@router.get("/methodology", response_model=MethodologyResponse, summary="Scoring and prompt versions")
def methodology(user: User = Depends(get_current_user)) -> MethodologyResponse:
    del user
    explainer = get_explainer()
    return MethodologyResponse(
        configured=explainer.configured,
        provider=explainer.name,
        **METHODOLOGY,
    )


@router.get("/analyses", response_model=ResearchListResponse, summary="The current user's research history")
def analyses(
    stock_id: UUID | None = None,
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResearchListResponse:
    rows, total = list_analyses(db, user, stock_id=stock_id, limit=limit, offset=offset)
    return ResearchListResponse(results=[_response(row) for row in rows], total=total, limit=limit, offset=offset)


@router.get("/analyses/{analysis_id}", response_model=ResearchResponse, summary="One owned research run")
def analysis(
    analysis_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResearchResponse:
    row = get_analysis(db, user, analysis_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return _response(row)


@router.get("/stocks/{stock_id}/latest", response_model=ResearchResponse, summary="Latest research for a stock")
def latest(
    stock_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResearchResponse:
    row = latest_analysis(db, user, stock_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return _response(row)


@router.post("/stocks/{stock_id}/analyses", response_model=ResearchResponse, status_code=201, summary="Run research for a stock")
def create(
    stock_id: UUID,
    refresh: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limiter: RateLimiter = Depends(get_rate_limiter),
) -> ResearchResponse:
    try:
        row = request_analysis(db, user, stock_id, refresh=refresh, limiter=limiter)
    except ResearchError as exc:
        raise HTTPException(status_code=_STATUS.get(exc.code, 422), detail=_detail(exc.code)) from None
    return _response(row)


def _detail(code: str) -> str:
    if code == "quota":
        return "Analysis limit reached. Try again later."
    return "Stock not found"
