from datetime import datetime
from typing import Any
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


class AuditLogActor(BaseModel):
    id: UUID
    display_name: str | None
    email: EmailStr


class AuditLogResource(BaseModel):
    type: str
    id: UUID | None = None
    label: str


class AuditLogListItem(BaseModel):
    id: UUID
    created_at: datetime
    action: str
    actor: AuditLogActor | None = None
    resource: AuditLogResource
    summary: str
    details: dict[str, Any] = Field(default_factory=dict)


class AuditLogListRead(BaseModel):
    items: list[AuditLogListItem]
    total: int
    page: int
    page_size: int
    pages: int
    available_actions: list[str] = Field(default_factory=list)
