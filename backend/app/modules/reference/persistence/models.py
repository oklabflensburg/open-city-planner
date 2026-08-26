"""Eigene ORM-Metadaten im ausschließlich vom Modul besessenen Schema."""

from datetime import datetime

from sqlalchemy import DateTime, Float, MetaData, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

METADATA = MetaData(schema="reference")


class ReferenceBase(DeclarativeBase):
    metadata = METADATA


class ReferenceItemRecord(ReferenceBase):
    __tablename__ = "items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
