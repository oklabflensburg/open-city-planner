from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.schemas.user import UserRead


def normalize_email(email: str) -> str:
    return email.strip().lower()


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12)
    first_name: str = Field(default="", max_length=120)
    last_name: str = Field(default="", max_length=120)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email_value(cls, value: str) -> str:
        return normalize_email(value)

    @field_validator("first_name", "last_name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return value.strip()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    remember: bool = True

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email_value(cls, value: str) -> str:
        return normalize_email(value)


class AuthResponse(BaseModel):
    user: UserRead
    csrf_token: str


class MessageResponse(BaseModel):
    message: str


class VerificationResponse(BaseModel):
    status: Literal["verified", "already_verified", "verification_sent"]
    code: Literal["EMAIL_VERIFIED", "EMAIL_ALREADY_VERIFIED", "VERIFICATION_EMAIL_SENT"]
    message: str


class TokenRequest(BaseModel):
    token: str = Field(min_length=20)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email_value(cls, value: str) -> str:
        return normalize_email(value)


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=20)
    password: str = Field(min_length=12)
    password_confirm: str = Field(min_length=12)

    @model_validator(mode="after")
    def passwords_match(self) -> "ResetPasswordRequest":
        if self.password != self.password_confirm:
            raise ValueError("Die Passwörter stimmen nicht überein.")
        return self


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=12)
    new_password_confirm: str = Field(min_length=12)

    @model_validator(mode="after")
    def passwords_match(self) -> "ChangePasswordRequest":
        if self.new_password != self.new_password_confirm:
            raise ValueError("Die neuen Passwörter stimmen nicht überein.")
        return self
