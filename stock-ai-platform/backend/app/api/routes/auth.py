from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, session_cookie
from app.core.cookies import clear_session_cookie, set_session_cookie
from app.core.database import get_db
from app.core.rate_limit import limit_auth
from app.models import User
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    ResetPasswordRequest,
    UserPublic,
)
from app.services.auth_service import (
    FORGOT_PASSWORD_MESSAGE,
    change_password,
    login_user,
    logout_user,
    register_user,
    request_password_reset,
    reset_password,
)
from app.services.email import EmailSender, get_email_sender

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Register a user",
)
def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    _: None = Depends(limit_auth("register", "register_rate_limit", "register_rate_window_seconds")),
) -> User:
    user, token = register_user(db, payload, request)
    set_session_cookie(response, token)
    return user


@router.post("/login", response_model=UserPublic, summary="Log in")
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    _: None = Depends(limit_auth("login", "login_rate_limit", "login_rate_window_seconds")),
) -> User:
    user, token = login_user(db, payload, request)
    set_session_cookie(response, token)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Log out")
def logout(
    response: Response,
    token: str | None = Depends(session_cookie),
    db: Session = Depends(get_db),
) -> None:
    logout_user(db, token)
    clear_session_cookie(response)


@router.get("/me", response_model=UserPublic, summary="Current authenticated user")
def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT, summary="Change password")
def change_password_route(
    payload: ChangePasswordRequest,
    response: Response,
    token: str | None = Depends(session_cookie),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    if token is None:
        clear_session_cookie(response)
        return
    rotated = change_password(db, user, token, payload)
    set_session_cookie(response, rotated)


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    summary="Request a password reset",
)
def forgot_password(
    payload: ForgotPasswordRequest,
    db: Session = Depends(get_db),
    sender: EmailSender = Depends(get_email_sender),
    _: None = Depends(
        limit_auth(
            "forgot-password",
            "forgot_password_rate_limit",
            "forgot_password_rate_window_seconds",
        )
    ),
) -> MessageResponse:
    request_password_reset(db, payload, sender)
    return MessageResponse(detail=FORGOT_PASSWORD_MESSAGE)


@router.post("/reset-password", response_model=MessageResponse, summary="Reset a password")
def reset_password_route(
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
    _: None = Depends(
        limit_auth(
            "reset-password",
            "reset_password_rate_limit",
            "reset_password_rate_window_seconds",
        )
    ),
) -> MessageResponse:
    reset_password(db, payload)
    return MessageResponse(detail="Password has been reset")
