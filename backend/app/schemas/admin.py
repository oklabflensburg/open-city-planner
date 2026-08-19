from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


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


class EmailCampaignWrite(BaseModel):
    internal_name: str = Field(min_length=1, max_length=180)
    subject: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=200)
    intro: str | None = Field(default=None, max_length=5_000)
    content_html: str = Field(min_length=1, max_length=50_000)
    content_text: str = Field(min_length=1, max_length=50_000)
    action_url: str | None = Field(default=None, max_length=2_048)
    action_label: str | None = Field(default=None, max_length=80)
    campaign_type: str = Field(pattern="^(LEGAL|SERVICE|NEWSLETTER|SYSTEM)$")
    recipient_scope: str = Field(pattern="^(ALL_ACTIVE_USERS|VERIFIED_USERS|SUPERUSERS)$")
    scheduled_at: datetime | None = None
    version: int | None = Field(default=None, ge=1)

    @field_validator("scheduled_at")
    @classmethod
    def scheduled_at_requires_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("Der Versandzeitpunkt benötigt eine Zeitzone.")
        return value


class EmailCampaignRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    internal_name: str
    subject: str
    title: str
    intro: str | None
    content_html: str
    content_text: str
    action_url: str | None
    action_label: str | None
    campaign_type: str
    status: str
    recipient_scope: str
    created_at: datetime
    updated_at: datetime
    scheduled_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    recipient_count: int
    sent_count: int
    failed_count: int
    skipped_count: int
    version: int


class EmailCampaignStart(BaseModel):
    legal_confirmed: bool = False


class EmailCampaignCountRead(BaseModel):
    recipient_count: int


class EmailUnsubscribeRequest(BaseModel):
    token: str = Field(min_length=20, max_length=512)


class EmailUnsubscribeRead(BaseModel):
    success: bool
    message: str
