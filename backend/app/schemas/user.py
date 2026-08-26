from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserRead(BaseModel):
    id: UUID
    email: EmailStr
    first_name: str
    last_name: str
    display_name: str | None
    avatar_url: str | None
    is_active: bool
    is_verified: bool
    email_pending: bool = False
    is_superuser: bool
    roles: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None

    model_config = ConfigDict(from_attributes=True)

    @field_validator("email_pending", mode="before")
    @classmethod
    def normalize_email_pending(cls, value: bool | None) -> bool:
        return bool(value)


class UserUpdate(BaseModel):
    first_name: str | None = Field(default=None, max_length=120)
    last_name: str | None = Field(default=None, max_length=120)
    display_name: str | None = Field(default=None, max_length=180)

    @field_validator("first_name", "last_name", "display_name")
    @classmethod
    def strip_optional(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value


class AccountDeletionRequest(BaseModel):
    confirmation_text: str = Field(min_length=1, max_length=32)
    current_password: str | None = Field(default=None, max_length=256)
