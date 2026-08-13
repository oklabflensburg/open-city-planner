from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class AdminRoleRead(BaseModel):
    name: str
    description: str


class AdminUserRead(BaseModel):
    id: UUID
    email: EmailStr
    first_name: str
    last_name: str
    display_name: str | None
    avatar_url: str | None
    is_active: bool
    is_verified: bool
    is_superuser: bool
    roles: list[str] = Field(default_factory=list)
    created_at: datetime
    last_login_at: datetime | None
    oauth_providers: list[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class AdminUserListRead(BaseModel):
    items: list[AdminUserRead]
    total: int
    page: int
    page_size: int


class AdminUserStatusUpdate(BaseModel):
    is_active: bool
