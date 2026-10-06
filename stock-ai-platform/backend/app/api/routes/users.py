from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import User
from app.schemas.auth import ProfileUpdate, UserPublic
from app.services.auth_service import update_profile

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/me", response_model=UserPublic, summary="Current user profile")
def read_profile(user: User = Depends(get_current_user)) -> User:
    """Return the authenticated user. A caller-supplied user id is not accepted."""
    return user


@router.patch("/me", response_model=UserPublic, summary="Update current user profile")
def patch_profile(
    payload: ProfileUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    return update_profile(db, user, payload)
