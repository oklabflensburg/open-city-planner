from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import BigInteger, CheckConstraint, DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OsmFeature(Base):
    """Read-only application view of locally imported OpenStreetMap features."""

    __tablename__ = "osm_features"

    osm_type: Mapped[str] = mapped_column(String(8), primary_key=True)
    osm_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    geometry: Mapped[object] = mapped_column(
        Geometry("GEOMETRY", srid=4326, spatial_index=False), nullable=False
    )
    tags: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "osm_type IN ('node', 'way', 'relation')", name="ck_osm_features_type"
        ),
        Index("idx_osm_features_geometry", "geometry", postgresql_using="gist"),
        Index("idx_osm_features_tags", "tags", postgresql_using="gin"),
    )
