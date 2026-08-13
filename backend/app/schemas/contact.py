from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator


class ContactMessageCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr = Field(max_length=320)
    subject: str = Field(min_length=3, max_length=160)
    message: str = Field(min_length=10, max_length=5000)
    website: str = Field(default="", max_length=200)
    form_token: str = Field(min_length=20, max_length=2048)
    turnstile_token: str | None = Field(default=None, max_length=2048)

    @field_validator("name", "subject", "message", mode="before")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("name", "subject")
    @classmethod
    def reject_header_injection(cls, value: str) -> str:
        if "\r" in value or "\n" in value:
            raise ValueError("Zeilenumbrüche sind hier nicht erlaubt.")
        return value


class ContactFormTokenResponse(BaseModel):
    form_token: str
    turnstile_enabled: bool
    turnstile_site_key: str | None = None


class ContactMessageResponse(BaseModel):
    status: Literal["sent"] = "sent"
    copy_sent: bool
