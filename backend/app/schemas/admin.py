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


class EmailTemplateListItemRead(BaseModel):
    key: str
    name: str
    description: str
    category: str
    customized: bool
    active: bool
    security_sensitive: bool
    version: int
    updated_at: datetime | None
    updated_by: str | None

    model_config = ConfigDict(from_attributes=True)


class EmailTemplateDetailRead(EmailTemplateListItemRead):
    subject: str
    html_body: str
    text_body: str
    allowed_variables: list[str]
    required_variables: list[str]


class EmailTemplateUpdate(BaseModel):
    subject: str = Field(max_length=200)
    html_body: str = Field(max_length=50_000)
    text_body: str = Field(max_length=50_000)
    version: int = Field(ge=0)


class EmailTemplateReset(BaseModel):
    version: int = Field(ge=0)


class EmailTemplatePreviewRead(BaseModel):
    subject: str
    html: str
    text: str


class EmailTemplateTestSendRead(BaseModel):
    message: str
