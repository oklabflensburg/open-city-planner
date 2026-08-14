import uuid as uuid_pkg
from datetime import UTC, datetime

from geoalchemy2 import Geometry
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class AnalysisArea(Base):
    __tablename__ = "analysis_areas"

    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[uuid_pkg.UUID] = mapped_column(UUID(as_uuid=True), default=uuid_pkg.uuid4, unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    area_type: Mapped[str] = mapped_column(String(16), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("analysis_areas.id", ondelete="SET NULL"))
    geometry: Mapped[object] = mapped_column(Geometry("MULTIPOLYGON", srid=4326, spatial_index=False), nullable=False)
    centroid: Mapped[object] = mapped_column(Geometry("POINT", srid=4326, spatial_index=False), nullable=False)
    area_m2: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String(24), default="OSM", nullable=False)
    source_osm_type: Mapped[str | None] = mapped_column(String(8))
    source_osm_id: Mapped[int | None] = mapped_column(BigInteger)
    source_admin_level: Mapped[int | None] = mapped_column(Integer)
    source_place: Mapped[str | None] = mapped_column(String(40))
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint("area_type IN ('MUNICIPALITY','DISTRICT','QUARTER')", name="ck_analysis_areas_type"),
        CheckConstraint("source IN ('OSM','MANUAL')", name="ck_analysis_areas_source"),
        UniqueConstraint("source", "source_osm_type", "source_osm_id", name="uq_analysis_areas_source_osm"),
        Index("idx_analysis_areas_parent", "parent_id"),
        Index("idx_analysis_areas_type", "area_type"),
        Index("idx_analysis_areas_geometry", "geometry", postgresql_using="gist"),
    )


class PolygonAnalysisArea(Base):
    __tablename__ = "polygon_analysis_areas"

    id: Mapped[int] = mapped_column(primary_key=True)
    polygon_id: Mapped[int] = mapped_column(ForeignKey("user_polygons.id", ondelete="CASCADE"), nullable=False)
    analysis_area_id: Mapped[int] = mapped_column(ForeignKey("analysis_areas.id", ondelete="CASCADE"), nullable=False)
    assignment_type: Mapped[str] = mapped_column(String(16), default="POINT_ON_SURFACE", nullable=False)
    overlap_ratio: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("polygon_id", "analysis_area_id", name="uq_polygon_analysis_area"),
        Index("idx_polygon_analysis_areas_polygon", "polygon_id"),
        Index("idx_polygon_analysis_areas_area", "analysis_area_id"),
    )
