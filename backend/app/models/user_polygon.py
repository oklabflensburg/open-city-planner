import uuid as uuid_pkg
from datetime import UTC, datetime
from decimal import Decimal

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class UserPolygon(Base):
    __tablename__ = "user_polygons"

    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[uuid_pkg.UUID] = mapped_column(
        UUID(as_uuid=True), default=uuid_pkg.uuid4, unique=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    floor: Mapped[str | None] = mapped_column(String(16))
    address_display_name: Mapped[str | None] = mapped_column(Text)
    address_street: Mapped[str | None] = mapped_column(String(160))
    address_house_number: Mapped[str | None] = mapped_column(String(40))
    address_postal_code: Mapped[str | None] = mapped_column(String(32))
    address_city: Mapped[str | None] = mapped_column(String(120))
    address_country: Mapped[str | None] = mapped_column(String(120))
    address_lookup_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    owner_name: Mapped[str | None] = mapped_column(String(200))
    owner_street: Mapped[str | None] = mapped_column(String(160))
    owner_house_number: Mapped[str | None] = mapped_column(String(40))
    owner_postal_code: Mapped[str | None] = mapped_column(String(32))
    owner_city: Mapped[str | None] = mapped_column(String(120))
    owner_country: Mapped[str | None] = mapped_column(String(120))
    price_per_sqm: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    category: Mapped[str] = mapped_column(String(80), default="custom", nullable=False)
    geometry: Mapped[object] = mapped_column(Geometry("POLYGON", srid=4326, spatial_index=False), nullable=False)
    properties: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    user_id: Mapped[str | None] = mapped_column(String(120))
    created_by_user_id: Mapped[uuid_pkg.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_user_id: Mapped[uuid_pkg.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    __table_args__ = (
        Index("idx_user_polygons_uuid", "uuid"),
        UniqueConstraint("slug", name="uq_user_polygons_slug"),
        Index("idx_user_polygons_created_at", "created_at"),
        Index("idx_user_polygons_created_by_user_id", "created_by_user_id"),
        Index("idx_user_polygons_updated_by_user_id", "updated_by_user_id"),
        Index("idx_user_polygons_category", "category"),
        Index("idx_user_polygons_floor", "floor"),
        Index("idx_user_polygons_geometry", "geometry", postgresql_using="gist"),
    )
