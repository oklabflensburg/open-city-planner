from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class OAuthIdentity(BaseModel):
    provider: str = Field(max_length=50)
    subject: str = Field(min_length=1, max_length=255)
    email: EmailStr | None = None
    email_verified: bool = False
    username: str | None = Field(default=None, max_length=255)
    display_name: str | None = Field(default=None, max_length=180)
    avatar_url: str | None = None

    @field_validator("provider")
    @classmethod
    def normalize_provider(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("subject")
    @classmethod
    def stringify_subject(cls, value: str) -> str:
        return str(value)


class UserOAuthAccountRead(BaseModel):
    id: UUID
    provider: str
    provider_username: str | None
    provider_email: EmailStr | None
    created_at: datetime
    last_login_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class OAuthProviderRead(BaseModel):
    id: str
    label: str
