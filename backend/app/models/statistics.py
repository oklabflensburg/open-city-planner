from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class StatisticalDataset(Base):
    __tablename__ = "statistical_datasets"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    external_dataset_id: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    license: Mapped[str] = mapped_column(String(160), nullable=False)
    update_frequency: Mapped[str] = mapped_column(String(40), nullable=False)
    last_import_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    __table_args__ = (
        UniqueConstraint("source", "external_dataset_id", name="uq_statistical_dataset_source"),
    )


class StatisticalMetric(Base):
    __tablename__ = "statistical_metrics"

    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_id: Mapped[int] = mapped_column(
        ForeignKey("statistical_datasets.id", ondelete="CASCADE"), nullable=False
    )
    key: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    unit: Mapped[str] = mapped_column(String(40), nullable=False)
    value_type: Mapped[str] = mapped_column(String(24), default="numeric", nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    aggregation_method: Mapped[str | None] = mapped_column(String(40))
    public: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    __table_args__ = (Index("idx_statistical_metrics_dataset", "dataset_id"),)


class ExternalAreaMapping(Base):
    __tablename__ = "external_area_mappings"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    external_area_id: Mapped[str] = mapped_column(String(80), nullable=False)
    external_area_name: Mapped[str] = mapped_column(String(200), nullable=False)
    level: Mapped[str] = mapped_column(String(40), nullable=False)
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    __table_args__ = (
        UniqueConstraint("source", "external_area_id", name="uq_external_area_mapping_id"),
        UniqueConstraint("source", "external_area_name", name="uq_external_area_mapping_name"),
        Index("idx_external_area_mapping_name_level", "external_area_name", "level"),
    )


class StatisticalObservation(Base):
    __tablename__ = "statistical_observations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    metric_id: Mapped[int] = mapped_column(
        ForeignKey("statistical_metrics.id", ondelete="CASCADE"), nullable=False
    )
    statistical_area_id: Mapped[int] = mapped_column(
        ForeignKey("external_area_mappings.id", ondelete="RESTRICT"), nullable=False
    )
    period_type: Mapped[str] = mapped_column(String(24), default="YEAR", nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    value_numeric: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    value_text: Mapped[str | None] = mapped_column(Text)
    source_area_id: Mapped[str] = mapped_column(String(80), nullable=False)
    source_row_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    is_calculated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint(
            "metric_id",
            "statistical_area_id",
            "period_start",
            "source_area_id",
            name="uq_statistical_observation",
        ),
        Index(
            "idx_statistical_observations_area_period",
            "statistical_area_id",
            "period_start",
        ),
        Index(
            "idx_statistical_observations_metric_period",
            "metric_id",
            "period_start",
        ),
    )


class StatisticalImportRun(Base):
    __tablename__ = "statistical_import_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    rows_downloaded: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rows_imported: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rows_updated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rows_unchanged: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rows_rejected: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    checksum: Mapped[str | None] = mapped_column(String(64))
    schema_hash: Mapped[str | None] = mapped_column(String(64))
    column_names: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("idx_statistical_import_runs_source_started", "source", "started_at"),
    )
