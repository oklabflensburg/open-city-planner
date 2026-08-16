import uuid as uuid_pkg
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UserOAuthAccount(Base):
    __tablename__ = "user_oauth_accounts"

    id: Mapped[uuid_pkg.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid_pkg.uuid4)
    user_id: Mapped[uuid_pkg.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_instance: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    provider_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_avatar_url: Mapped[str | None] = mapped_column(Text(), nullable=True)
    provider_profile_url: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="oauth_accounts")

    __table_args__ = (
        UniqueConstraint("user_id", "provider", name="uq_user_oauth_accounts_user_provider"),
        Index(
            "uq_user_oauth_accounts_central_identity",
            "provider",
            "provider_subject",
            unique=True,
            postgresql_where=text("provider_instance IS NULL"),
        ),
        Index(
            "uq_user_oauth_accounts_federated_identity",
            "provider",
            "provider_instance",
            "provider_subject",
            unique=True,
            postgresql_where=text("provider_instance IS NOT NULL"),
        ),
        Index("idx_user_oauth_accounts_user_id", "user_id"),
        Index("idx_user_oauth_accounts_provider", "provider"),
    )


class MastodonOAuthInstance(Base):
    __tablename__ = "mastodon_oauth_instances"

    id: Mapped[uuid_pkg.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid_pkg.uuid4
    )
    instance_origin: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    client_id_encrypted: Mapped[str | None] = mapped_column(Text(), nullable=True)
    client_secret_encrypted: Mapped[str | None] = mapped_column(Text(), nullable=True)
    oauth_scope: Mapped[str | None] = mapped_column(String(64), nullable=True)
    software_version: Mapped[str | None] = mapped_column(String(120), nullable=True)
    registration_failure_count: Mapped[int] = mapped_column(Integer(), default=0, nullable=False)
    registration_retry_after: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class OAuthFlowGrant(Base):
    __tablename__ = "oauth_flow_grants"

    state_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    redirect_path: Mapped[str] = mapped_column(Text(), nullable=False)
    user_id: Mapped[uuid_pkg.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    instance_origin: Mapped[str] = mapped_column(String(255), nullable=False)
    code_verifier: Mapped[str] = mapped_column(String(128), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_oauth_flow_grants_expires_at", "expires_at"),
    )
