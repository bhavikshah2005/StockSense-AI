from fastapi import Depends, HTTPException, Request
from fastapi.security import APIKeyCookie
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models import User
from app.services.auth_service import NOT_AUTHENTICATED, current_session

session_cookie = APIKeyCookie(name=settings.session_cookie_name, auto_error=False)


def get_current_user(
    request: Request,
    token: str | None = Depends(session_cookie),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the user from the session cookie. Client-supplied user ids are ignored."""
    del request
    session = current_session(db, token)
    if session is None:
        raise HTTPException(status_code=401, detail=NOT_AUTHENTICATED)
    return session.user
