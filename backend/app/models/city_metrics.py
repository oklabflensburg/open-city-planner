import uuid as uuid_pkg
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class CityMetrics(Base):
    """Centrally maintained city-wide metrics; percentage values use percentage points."""

    __tablename__ = "city_metrics"

    id: Mapped[uuid_pkg.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid_pkg.uuid4
    )
    vacancy_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    chain_store_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    centrality_index: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    purchasing_power_index: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    reference_date: Mapped[date | None] = mapped_column(Date)
    source: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
    updated_by_user_id: Mapped[uuid_pkg.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
