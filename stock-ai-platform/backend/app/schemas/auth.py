from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

from app.core.passwords import validate_password_strength


def _normalize_email(value: object) -> object:
    if isinstance(value, str):
        return value.strip().lower()
    return value


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    full_name: str | None
    is_active: bool
    created_at: datetime


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str
    full_name: str

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        return _normalize_email(value)

    @field_validator("password")
    @classmethod
    def check_password(cls, value: str) -> str:
        validate_password_strength(value)
        return value

    @field_validator("full_name")
    @classmethod
    def check_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned or len(cleaned) > 255:
            raise ValueError("Full name must be 1 to 255 characters")
        return cleaned


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        return _normalize_email(value)


class ChangePasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def check_password(cls, value: str) -> str:
        validate_password_strength(value)
        return value


class ForgotPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        return _normalize_email(value)


class ResetPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def check_password(cls, value: str) -> str:
        validate_password_strength(value)
        return value


class MessageResponse(BaseModel):
    detail: str


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str

    @field_validator("full_name")
    @classmethod
    def check_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned or len(cleaned) > 255:
            raise ValueError("Full name must be 1 to 255 characters")
        return cleaned
