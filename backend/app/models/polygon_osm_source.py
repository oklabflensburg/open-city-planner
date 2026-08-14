from datetime import UTC, datetime

from geoalchemy2 import Geometry
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PolygonOsmSource(Base):
    __tablename__ = "polygon_osm_sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    polygon_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("user_polygons.id", ondelete="CASCADE"), nullable=False
    )
    osm_type: Mapped[str] = mapped_column(String(8), nullable=False)
    osm_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    osm_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    source_geometry: Mapped[object] = mapped_column(
        Geometry("GEOMETRY", srid=4326, spatial_index=False), nullable=False
    )
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("polygon_id", "osm_type", "osm_id", name="uq_polygon_osm_source"),
        Index("idx_polygon_osm_sources_osm", "osm_type", "osm_id"),
        Index("idx_polygon_osm_sources_polygon", "polygon_id"),
    )
