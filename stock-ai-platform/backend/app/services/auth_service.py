import logging
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    dummy_password_check,
    generate_secret,
    hash_password,
    hash_secret,
    password_needs_rehash,
    verify_password,
)
from app.models import PasswordResetToken, User, UserSession
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    ProfileUpdate,
    RegisterRequest,
    ResetPasswordRequest,
)
from app.services.email import EmailSender, PasswordResetEmail

logger = logging.getLogger(__name__)

INVALID_CREDENTIALS = "Invalid email or password"
NOT_AUTHENTICATED = "Not authenticated"
FORGOT_PASSWORD_MESSAGE = "If the account exists, password reset instructions have been sent."


def register_user(db: Session, payload: RegisterRequest, request: Request) -> tuple[User, str]:
    existing = db.scalar(select(User.id).where(User.email == payload.email))
    if existing is not None:
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        is_active=True,
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="An account with this email already exists",
        ) from None

    token = _start_session(db, user, request)
    db.commit()
    db.refresh(user)
    return user, token


def login_user(db: Session, payload: LoginRequest, request: Request) -> tuple[User, str]:
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None:
        dummy_password_check(payload.password)
        logger.info("Login failed")
        raise HTTPException(status_code=401, detail=INVALID_CREDENTIALS)

    if not verify_password(payload.password, user.password_hash) or not user.is_active:
        logger.info("Login failed")
        raise HTTPException(status_code=401, detail=INVALID_CREDENTIALS)

    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(payload.password)

    token = _start_session(db, user, request)
    db.commit()
    db.refresh(user)
    return user, token


def logout_user(db: Session, token: str | None) -> None:
    session = _session_for_token(db, token)
    if session is not None and session.revoked_at is None:
        session.revoked_at = datetime.now(UTC)
        db.commit()


def current_session(db: Session, token: str | None) -> UserSession | None:
    session = _session_for_token(db, token)
    if session is None or session.revoked_at is not None:
        return None
    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at <= datetime.now(UTC):
        return None
    if not session.user.is_active:
        return None
    session.last_used_at = datetime.now(UTC)
    db.commit()
    return session


def change_password(
    db: Session,
    user: User,
    current_token: str,
    payload: ChangePasswordRequest,
) -> str:
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    user.password_hash = hash_password(payload.new_password)
    now = datetime.now(UTC)
    current = _session_for_token(db, current_token)
    for session in db.scalars(select(UserSession).where(UserSession.user_id == user.id)):
        if current is not None and session.id == current.id:
            continue
        if session.revoked_at is None:
            session.revoked_at = now
    rotated = generate_secret()
    if current is None:
        raise HTTPException(status_code=401, detail=NOT_AUTHENTICATED)
    current.token_hash = hash_secret(rotated)
    current.last_used_at = now
    db.commit()
    return rotated


def request_password_reset(
    db: Session,
    payload: ForgotPasswordRequest,
    sender: EmailSender,
) -> None:
    user = db.scalar(select(User).where(User.email == payload.email, User.is_active.is_(True)))
    if user is None:
        return
    token = generate_secret()
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_secret(token),
            expires_at=datetime.now(UTC) + timedelta(minutes=settings.password_reset_expire_minutes),
        )
    )
    db.commit()
    origin = settings.allowed_origins[0]
    sender.send_password_reset(
        PasswordResetEmail(
            recipient=user.email,
            reset_url=f"{origin}/reset-password?token={token}",
        )
    )


def reset_password(db: Session, payload: ResetPasswordRequest) -> None:
    token_row = db.scalar(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_secret(payload.token))
    )
    now = datetime.now(UTC)
    if token_row is None or token_row.used_at is not None:
        raise HTTPException(status_code=400, detail="Invalid or expired password reset token")
    expires_at = token_row.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at <= now:
        raise HTTPException(status_code=400, detail="Invalid or expired password reset token")

    user = db.get(User, token_row.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=400, detail="Invalid or expired password reset token")

    user.password_hash = hash_password(payload.new_password)
    token_row.used_at = now
    for session in db.scalars(select(UserSession).where(UserSession.user_id == user.id)):
        if session.revoked_at is None:
            session.revoked_at = now
    db.commit()


def update_profile(db: Session, user: User, payload: ProfileUpdate) -> User:
    user.full_name = payload.full_name
    db.commit()
    db.refresh(user)
    return user


def _start_session(db: Session, user: User, request: Request) -> str:
    token = generate_secret()
    now = datetime.now(UTC)
    user_agent = request.headers.get("user-agent")
    db.add(
        UserSession(
            user_id=user.id,
            token_hash=hash_secret(token),
            expires_at=now + timedelta(minutes=settings.session_expire_minutes),
            last_used_at=now,
            user_agent=user_agent[:512] if user_agent else None,
            ip_address=request.client.host if request.client is not None else None,
        )
    )
    db.flush()
    return token


def _session_for_token(db: Session, token: str | None) -> UserSession | None:
    if not token:
        return None
    return db.scalar(select(UserSession).where(UserSession.token_hash == hash_secret(token)))
