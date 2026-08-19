import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

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
    status: Literal["authenticated"] = "authenticated"
    user: UserRead
    csrf_token: str


class MfaChallengeResponse(BaseModel):
    status: Literal["mfa_required"] = "mfa_required"
    challenge_token: str
    method: Literal["passkey", "totp"] = "totp"
    methods: list[Literal["passkey", "totp", "recovery_code"]] = Field(
        default_factory=lambda: ["totp", "recovery_code"]
    )
    expires_in: int


LoginResponse = Annotated[AuthResponse | MfaChallengeResponse, Field(discriminator="status")]


class MfaVerifyRequest(BaseModel):
    challenge_token: str = Field(min_length=32, max_length=512)
    code: str | None = Field(default=None, min_length=6, max_length=8)
    recovery_code: str | None = Field(default=None, min_length=12, max_length=32)

    @model_validator(mode="after")
    def exactly_one_code(self) -> "MfaVerifyRequest":
        if bool(self.code) == bool(self.recovery_code):
            raise ValueError("Geben Sie genau einen Authenticator- oder Wiederherstellungscode an.")
        return self


class TotpSetupResponse(BaseModel):
    secret: str
    otpauth_uri: str
    issuer: str
    account_name: str
    expires_in: int


class TotpConfirmRequest(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")


class RecoveryCodesResponse(BaseModel):
    recovery_codes: list[str]


class MfaDisableRequest(BaseModel):
    current_password: str | None = Field(default=None, max_length=512)
    code: str | None = Field(default=None, min_length=6, max_length=8)
    recovery_code: str | None = Field(default=None, min_length=12, max_length=32)

    @model_validator(mode="after")
    def exactly_one_factor(self) -> "MfaDisableRequest":
        if bool(self.code) == bool(self.recovery_code):
            raise ValueError("Geben Sie genau einen Authenticator- oder Wiederherstellungscode an.")
        return self


class MfaRegenerateRequest(MfaDisableRequest):
    pass


class MfaSecurityStatus(BaseModel):
    enabled: bool
    method: Literal["totp"] | None = None
    enabled_at: datetime | None = None
    last_used_at: datetime | None = None
    recovery_codes_remaining: int = 0


class WebAuthnOptionsResponse(BaseModel):
    ceremony_token: str
    options: dict[str, Any]


class PasskeyRegistrationVerifyRequest(BaseModel):
    ceremony_token: str = Field(min_length=32, max_length=512)
    credential: dict[str, Any]
    name: str | None = Field(default=None, min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def strip_optional_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("Der Passkey-Name darf nicht leer sein.")
        return stripped


class PasskeyAuthenticationVerifyRequest(BaseModel):
    ceremony_token: str = Field(min_length=32, max_length=512)
    credential: dict[str, Any]


class PasskeyMfaOptionsRequest(BaseModel):
    challenge_token: str = Field(min_length=32, max_length=512)


class PasskeyMfaVerifyRequest(PasskeyAuthenticationVerifyRequest):
    challenge_token: str = Field(min_length=32, max_length=512)


class PasskeyRead(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime
    updated_at: datetime
    last_used_at: datetime | None
    device_type: str | None
    backed_up: bool | None
    transports: list[str] | None

    model_config = {"from_attributes": True}


class PasskeyRenameRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Der Passkey-Name darf nicht leer sein.")
        return stripped


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
