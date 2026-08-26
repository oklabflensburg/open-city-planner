"""Fachkern des Referenzmoduls ohne Framework-Abhängigkeiten."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class ReferenceItem:
    id: str
    title: str
    description: str
    longitude: float
    latitude: float
    created_at: datetime
