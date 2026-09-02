"""Öffentliches Backend-SDK für Open-City-Planner-Module.

Dieses Modul ist der stabile Importpfad für Modulcode. Es definiert ausschließlich
Plattform-Ports und importiert keine Host-Infrastruktur oder Fachdomänen.
"""

import logging
import math
import posixpath
import re
from collections.abc import Awaitable, Callable, Mapping, Sequence
from contextlib import AbstractAsyncContextManager, AbstractContextManager
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from types import MappingProxyType
from typing import ClassVar, Literal, Protocol, TypeVar, overload
from uuid import UUID, uuid4

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.modules.manifest import (
    ManifestInput,
    ModuleManifestV1,
    parse_manifest,
)

type ModuleLifecycleHook = Callable[[], Awaitable[None]]
type ModuleLoader = Callable[[], "BackendModule"]
type JobHandler = Callable[["ModuleContext"], Awaitable[object | None]]
type LegacyJobHandler = Callable[[], Awaitable[object | None]]
type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | list["JsonValue"] | Mapping[str, "JsonValue"]
T = TypeVar("T")
TSettings = TypeVar("TSettings", bound=BaseModel)
_EVENT_NAME = re.compile(r"^[a-z][a-z0-9-]*(?:\.[a-z][a-z0-9-]*)+$")
_JOB_NAME = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
_REVISION_NAMESPACE = re.compile(r"^mod_[a-z][a-z0-9_]*$")
_PYTHON_IMPORT_PACKAGE = re.compile(r"^[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*$")


class ApiRegistrar(Protocol):
    """Registriert vom Host kontrolliert einzubindende FastAPI-Router."""

    def include_router(
        self,
        router: APIRouter,
        *,
        prefix: str = "",
        tags: Sequence[str] = (),
    ) -> None: ...


class LifecycleRegistrar(Protocol):
    """Registriert asynchrone Hooks ohne externe Side Effects während register()."""

    def add_lifecycle(
        self,
        *,
        startup: ModuleLifecycleHook | None = None,
        shutdown: ModuleLifecycleHook | None = None,
    ) -> None: ...


class DatabaseSessionProvider(Protocol):
    """Öffnet eine vom Host verwaltete SQLAlchemy-Session."""

    def session(self) -> AbstractAsyncContextManager[AsyncSession]: ...


@dataclass(frozen=True, slots=True)
class ModuleMigrationSource:
    """Installierte, lokale Alembic-Quelle eines Moduls."""

    package: str
    resource: str
    revision_namespace: str
    adopted_revisions: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if not _PYTHON_IMPORT_PACKAGE.fullmatch(self.package):
            raise ValueError("Migration packages must be installed Python package names.")
        normalized = posixpath.normpath(self.resource)
        if (
            not self.resource
            or self.resource.startswith(("/", "\\"))
            or normalized in {".", ".."}
            or normalized.startswith("../")
            or "://" in self.resource
            or "\\" in self.resource
        ):
            raise ValueError("Migration resources must be relative installed-package paths.")
        if not _REVISION_NAMESPACE.fullmatch(self.revision_namespace):
            raise ValueError('Revision namespaces must use the form "mod_<module_id>".')
        if not isinstance(self.adopted_revisions, frozenset):
            raise TypeError("Adopted migration revisions must be an immutable frozenset.")
        if any(
            not isinstance(revision, str)
            or not revision
            or revision != revision.strip()
            for revision in self.adopted_revisions
        ):
            raise ValueError("Adopted migration revisions must be non-empty exact IDs.")


@dataclass(frozen=True, slots=True)
class ModulePersistenceContribution:
    """Passive ORM- und Migrationsmetadaten einer ModuleDefinition."""

    module_id: str
    metadata: MetaData
    schema: str
    migration_source: ModuleMigrationSource | None = None
    adopted_tables: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        for table_name in self.adopted_tables:
            if not re.fullmatch(r"[a-z_][a-z0-9_]*", table_name):
                raise ValueError("Adopted table names must be unqualified PostgreSQL identifiers.")


@dataclass(frozen=True, slots=True)
class ModuleSettingsContribution:
    """Passives, vom Modul besessenes Schema für dessen namespacete Konfiguration."""

    module_id: str
    namespace: str
    model: type[BaseModel]


class DomainEvent(Protocol):
    """Kompatible minimale Event-Identität aus SDK 1.0."""

    event_type: str
    event_version: int


class SerializableDomainEvent(Protocol):
    """Vom Producer besessener, stark typisierbarer Event-Payload-Contract."""

    event_name: str
    event_version: int

    def to_payload(self) -> Mapping[str, JsonValue]: ...


@dataclass(frozen=True, slots=True)
class EventEnvelope:
    """Fachneutraler, persistierbarer Event-Envelope mit stabiler Identität."""

    event_id: UUID
    event_name: str
    event_version: int
    occurred_at: datetime
    payload: Mapping[str, JsonValue]
    correlation_id: str | None = None
    causation_id: str | None = None
    trace_context: Mapping[str, str] = MappingProxyType({})
    producer_module: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.event_id, UUID):
            raise TypeError("Event IDs must be UUID values.")
        if not isinstance(self.event_name, str) or not _EVENT_NAME.fullmatch(self.event_name):
            raise ValueError("Event names must use the form <module-id>.<event-name>.")
        if len(self.event_name) > 160:
            raise ValueError("Event names must not exceed 160 characters.")
        if type(self.event_version) is not int or self.event_version < 1:
            raise ValueError("Event versions must be positive integers.")
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise ValueError("Event timestamps must include a timezone.")
        if self.occurred_at.utcoffset() != UTC.utcoffset(self.occurred_at):
            raise ValueError("Event timestamps must use UTC.")
        if not isinstance(self.payload, Mapping):
            raise TypeError("Event payloads must be JSON objects.")
        _validate_json_value(self.payload, path="payload")
        _validate_string_mapping(self.trace_context, name="trace_context")
        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))
        object.__setattr__(self, "trace_context", MappingProxyType(dict(self.trace_context)))


type EventHandler = Callable[[EventEnvelope], Awaitable[None] | None]


def event_envelope(
    event: DomainEvent | SerializableDomainEvent,
    *,
    event_id: UUID | None = None,
    occurred_at: datetime | None = None,
    correlation_id: str | None = None,
    causation_id: str | None = None,
    trace_context: Mapping[str, str] | None = None,
) -> EventEnvelope:
    """Erzeuge Metadaten für ein fachlich typisiertes Event ohne implizite Serialisierung."""

    event_name = getattr(event, "event_name", None) or event.event_type
    serializer = getattr(event, "to_payload", None)
    payload = serializer() if serializer is not None else {}
    return EventEnvelope(
        event_id=event_id or uuid4(),
        event_name=event_name,
        event_version=event.event_version,
        occurred_at=occurred_at or datetime.now(UTC),
        payload=payload,
        correlation_id=correlation_id,
        causation_id=causation_id,
        trace_context=trace_context or {},
    )


def _validate_json_value(value: object, *, path: str) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{path} contains a non-finite number.")
    if value is None or isinstance(value, str | bool | int | float):
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json_value(item, path=f"{path}[{index}]")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(f"{path} contains a non-string object key.")
            _validate_json_value(item, path=f"{path}.{key}")
        return
    raise TypeError(f"{path} contains the non-JSON value {type(value).__name__}.")


def _validate_string_mapping(value: Mapping[object, object], *, name: str) -> None:
    if not all(isinstance(key, str) and isinstance(item, str) for key, item in value.items()):
        raise TypeError(f"{name} must contain only string keys and values.")


class EventBusPort(Protocol):
    """Publiziert Events direkt oder atomar über die transaktionale Outbox."""

    async def publish(
        self, event: DomainEvent | SerializableDomainEvent | EventEnvelope
    ) -> None: ...

    async def publish_after_commit(
        self,
        event: DomainEvent | SerializableDomainEvent | EventEnvelope,
        *,
        session: AsyncSession,
    ) -> EventEnvelope: ...

    def subscribe(
        self,
        event_name: str,
        *,
        handler_id: str,
        versions: frozenset[int],
        handler: EventHandler,
    ) -> None: ...


class ServiceRegistryPort(Protocol):
    """Registriert und löst explizite öffentliche Cross-Module-Contracts auf."""

    def register(
        self,
        contract: type[T],
        implementation: T,
        *,
        service_id: str,
        version: int,
        deprecated_since: str | None = None,
        replacement: str | None = None,
    ) -> None: ...

    def require(self, contract: type[T], *, service_id: str, version: int) -> T: ...

    def optional(self, contract: type[T], *, service_id: str, version: int) -> T | None: ...

    def resolve(self, contract: type[T]) -> T: ...


OSM_SNAPSHOT_QUERY_SERVICE_ID = "platform.osm-snapshot-query"
OSM_SNAPSHOT_QUERY_SERVICE_VERSION = 1
OSM_POSTPROCESSING_COMPLETED_EVENT = "osm.postprocessing-completed"
OSM_POSTPROCESSING_COMPLETED_EVENT_VERSION = 1
OSM_SNAPSHOT_MAX_PAGE_SIZE = 500
POLYGON_SPATIAL_MATCH_MAX_AREAS = 5000
POLYGON_SPATIAL_MATCH_SERVICE_ID = "platform.polygon-spatial-match"
POLYGON_SPATIAL_MATCH_SERVICE_VERSION = 1
POLYGON_IDENTITY_MAX_UUIDS = 5000
POLYGON_IDENTITY_SERVICE_ID = "platform.polygon-identity"
POLYGON_IDENTITY_SERVICE_VERSION = 1

type OsmType = Literal["node", "way", "relation"]
type OsmGeometryKind = Literal["point", "area"]


@dataclass(frozen=True, slots=True)
class OsmFeatureCursor:
    """Exklusiver, stabiler Cursor in OSM-Typ-/ID-Reihenfolge."""

    osm_type: OsmType
    osm_id: int

    def __post_init__(self) -> None:
        if self.osm_type not in {"node", "way", "relation"}:
            raise ValueError("OSM types must be node, way, or relation.")
        if type(self.osm_id) is not int or self.osm_id < 0:
            raise ValueError("OSM IDs must be non-negative integers.")


@dataclass(frozen=True, slots=True)
class OsmTagFilter:
    """Fordert einen Tag-Schlüssel und optional einen seiner Werte."""

    key: str
    values: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if (
            not self.key
            or self.key != self.key.strip()
            or "\x00" in self.key
            or len(self.key) > 255
        ):
            raise ValueError("OSM tag keys must be non-empty normalized text.")
        if not isinstance(self.values, tuple) or any(
            not isinstance(value, str) or "\x00" in value or len(value) > 1024
            for value in self.values
        ):
            raise TypeError("OSM tag filter values must be an immutable tuple of strings.")
        if len(self.values) > 50 or len(set(self.values)) != len(self.values):
            raise ValueError("OSM tag filters allow at most 50 unique values.")


def _validate_osm_bbox(
    value: tuple[float, float, float, float], *, allow_degenerate: bool
) -> None:
    if not isinstance(value, tuple) or len(value) != 4:
        raise TypeError("OSM bounding boxes must be immutable four-value tuples.")
    west, south, east, north = value
    if not all(type(item) in (int, float) and math.isfinite(item) for item in value):
        raise ValueError("OSM bounding boxes must contain finite numbers.")
    if allow_degenerate:
        ordered = west <= east and south <= north
    else:
        ordered = west < east and south < north
    if not (-180 <= west <= east <= 180 and -90 <= south <= north <= 90 and ordered):
        raise ValueError("OSM bounding boxes must be valid EPSG:4326 bounds.")


@dataclass(frozen=True, slots=True)
class OsmSnapshotQuery:
    """Begrenzte, fachneutrale Filter für einen unveränderlichen OSM-Snapshot."""

    osm_types: tuple[OsmType, ...] = ()
    geometry_kinds: tuple[OsmGeometryKind, ...] = ()
    required_tag_keys: tuple[str, ...] = ()
    tag_filters: tuple[OsmTagFilter, ...] = ()
    bbox: tuple[float, float, float, float] | None = None
    cursor: OsmFeatureCursor | None = None
    limit: int = 100

    def __post_init__(self) -> None:
        if not isinstance(self.osm_types, tuple) or any(
            value not in {"node", "way", "relation"} for value in self.osm_types
        ):
            raise ValueError("OSM types must be an immutable tuple of supported values.")
        if len(self.osm_types) > 3 or len(set(self.osm_types)) != len(self.osm_types):
            raise ValueError("OSM types must contain unique supported values.")
        if not isinstance(self.geometry_kinds, tuple) or any(
            value not in {"point", "area"} for value in self.geometry_kinds
        ):
            raise ValueError("OSM geometry kinds must be point or area.")
        if len(self.geometry_kinds) > 2 or len(set(self.geometry_kinds)) != len(
            self.geometry_kinds
        ):
            raise ValueError("OSM geometry kinds must contain unique supported values.")
        if not isinstance(self.required_tag_keys, tuple) or any(
            not isinstance(key, str)
            or not key
            or key != key.strip()
            or "\x00" in key
            or len(key) > 255
            for key in self.required_tag_keys
        ):
            raise ValueError("Required OSM tag keys must be normalized strings.")
        if len(self.required_tag_keys) > 20 or len(set(self.required_tag_keys)) != len(
            self.required_tag_keys
        ):
            raise ValueError("OSM snapshot queries allow at most 20 unique required tag keys.")
        if not isinstance(self.tag_filters, tuple) or not all(
            isinstance(value, OsmTagFilter) for value in self.tag_filters
        ):
            raise TypeError("OSM tag filters must be an immutable tuple.")
        if len(self.tag_filters) > 20 or len({item.key for item in self.tag_filters}) != len(
            self.tag_filters
        ):
            raise ValueError("OSM snapshot queries allow at most 20 unique tag filters.")
        if self.cursor is not None and not isinstance(self.cursor, OsmFeatureCursor):
            raise TypeError("OSM snapshot cursors must use OsmFeatureCursor.")
        if type(self.limit) is not int or not 1 <= self.limit <= OSM_SNAPSHOT_MAX_PAGE_SIZE:
            raise ValueError(
                f"OSM snapshot limits must be between 1 and {OSM_SNAPSHOT_MAX_PAGE_SIZE}."
            )
        if self.bbox is not None:
            _validate_osm_bbox(self.bbox, allow_degenerate=False)


@dataclass(frozen=True, slots=True)
class OsmFeatureSnapshot:
    """ORM-freie OSM-Leseprojektion; Geometrie ist EWKB in EPSG:4326."""

    osm_type: OsmType
    osm_id: int
    tags: Mapping[str, str]
    geometry_wkb: bytes
    bbox: tuple[float, float, float, float]
    imported_at: datetime

    def __post_init__(self) -> None:
        OsmFeatureCursor(self.osm_type, self.osm_id)
        _validate_string_mapping(self.tags, name="tags")
        if not isinstance(self.geometry_wkb, bytes):
            raise TypeError("OSM snapshot geometry must be immutable EWKB bytes.")
        _validate_osm_bbox(self.bbox, allow_degenerate=True)
        if self.imported_at.tzinfo is None or self.imported_at.utcoffset() is None:
            raise ValueError("OSM import timestamps must include a timezone.")
        object.__setattr__(self, "tags", MappingProxyType(dict(self.tags)))


@dataclass(frozen=True, slots=True)
class OsmFeatureSnapshotPage:
    items: tuple[OsmFeatureSnapshot, ...]
    next_cursor: OsmFeatureCursor | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.items, tuple) or not all(
            isinstance(item, OsmFeatureSnapshot) for item in self.items
        ):
            raise TypeError("OSM snapshot pages must contain an immutable tuple of DTOs.")
        if self.next_cursor is not None and not isinstance(
            self.next_cursor, OsmFeatureCursor
        ):
            raise TypeError("OSM snapshot next cursors must use OsmFeatureCursor.")


class OsmSnapshotQueryPort(Protocol):
    async def list_features(
        self, session: AsyncSession, query: OsmSnapshotQuery
    ) -> OsmFeatureSnapshotPage: ...


def _validate_polygon_spatial_text(value: str, *, name: str, max_length: int) -> None:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or "\x00" in value
        or len(value) > max_length
    ):
        raise ValueError(f"Polygon spatial {name} must be non-empty normalized text.")


@dataclass(frozen=True, slots=True)
class PolygonSpatialArea:
    """Gebietsreferenz mit EWKB-Geometrie in EPSG:4326."""

    external_id: str
    selection_group: str
    geometry_wkb: bytes

    def __post_init__(self) -> None:
        _validate_polygon_spatial_text(
            self.external_id, name="area IDs", max_length=255
        )
        _validate_polygon_spatial_text(
            self.selection_group, name="selection groups", max_length=100
        )
        if not isinstance(self.geometry_wkb, bytes) or not self.geometry_wkb:
            raise ValueError("Polygon spatial geometries must be non-empty EWKB bytes.")


@dataclass(frozen=True, slots=True)
class PolygonSpatialMatchRequest:
    """Gebietsgeometrien für eine rein lesende räumliche Polygon-Auswahl."""

    areas: tuple[PolygonSpatialArea, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.areas, tuple) or not all(
            isinstance(area, PolygonSpatialArea) for area in self.areas
        ):
            raise TypeError("Polygon spatial requests require an immutable tuple of areas.")
        if len(self.areas) > POLYGON_SPATIAL_MATCH_MAX_AREAS:
            raise ValueError(
                f"Polygon spatial requests allow at most {POLYGON_SPATIAL_MATCH_MAX_AREAS} areas."
            )
        external_ids = tuple(area.external_id for area in self.areas)
        if len(set(external_ids)) != len(external_ids):
            raise ValueError("Polygon spatial area IDs must be unique per request.")


@dataclass(frozen=True, slots=True)
class PolygonSpatialMatch:
    polygon_id: str
    external_area_id: str
    selection_group: str
    overlap_ratio: float | None

    def __post_init__(self) -> None:
        try:
            polygon_id = UUID(self.polygon_id)
        except (TypeError, ValueError, AttributeError) as exc:
            raise ValueError("Polygon match IDs must be UUID strings.") from exc
        if str(polygon_id) != self.polygon_id:
            raise ValueError("Polygon match IDs must be canonical UUID strings.")
        _validate_polygon_spatial_text(
            self.external_area_id, name="area IDs", max_length=255
        )
        _validate_polygon_spatial_text(
            self.selection_group, name="selection groups", max_length=100
        )
        if self.overlap_ratio is not None and (
            type(self.overlap_ratio) not in (int, float)
            or not math.isfinite(self.overlap_ratio)
            or not 0 <= self.overlap_ratio <= 1
        ):
            raise ValueError("Polygon overlap ratios must be finite values from zero to one.")


@dataclass(frozen=True, slots=True)
class PolygonSpatialMatchResult:
    matches: tuple[PolygonSpatialMatch, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.matches, tuple) or not all(
            isinstance(match, PolygonSpatialMatch) for match in self.matches
        ):
            raise TypeError("Polygon spatial results require an immutable tuple of matches.")


class PolygonSpatialMatchPort(Protocol):
    async def match_polygons(
        self, session: AsyncSession, request: PolygonSpatialMatchRequest
    ) -> PolygonSpatialMatchResult: ...


@dataclass(frozen=True, slots=True)
class PolygonIdentity:
    """Host-interne Polygon-ID zu ihrer stabilen öffentlichen UUID."""

    id: int
    uuid: UUID

    def __post_init__(self) -> None:
        if type(self.id) is not int or self.id < 1:
            raise ValueError("Polygon identity IDs must be positive integers.")
        if not isinstance(self.uuid, UUID):
            raise TypeError("Polygon identity UUIDs must be UUID values.")


@dataclass(frozen=True, slots=True)
class PolygonIdentityRequest:
    """Begrenzte stabile Polygon-UUIDs in eindeutiger Eingabereihenfolge."""

    polygon_uuids: tuple[UUID, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.polygon_uuids, tuple):
            raise TypeError("Polygon identity requests require an immutable tuple.")
        if not all(isinstance(value, UUID) for value in self.polygon_uuids):
            raise TypeError("Polygon identity requests require UUID values.")
        if len(self.polygon_uuids) > POLYGON_IDENTITY_MAX_UUIDS:
            raise ValueError(
                f"Polygon identity requests allow at most {POLYGON_IDENTITY_MAX_UUIDS} UUIDs."
            )
        object.__setattr__(self, "polygon_uuids", tuple(dict.fromkeys(self.polygon_uuids)))


@dataclass(frozen=True, slots=True)
class PolygonIdentityResult:
    """Aufgelöste Identitäten und explizit nicht gefundene UUIDs."""

    resolved: tuple[PolygonIdentity, ...]
    missing: tuple[UUID, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.resolved, tuple) or not all(
            isinstance(value, PolygonIdentity) for value in self.resolved
        ):
            raise TypeError("Resolved polygon identities must be an immutable tuple.")
        if not isinstance(self.missing, tuple) or not all(
            isinstance(value, UUID) for value in self.missing
        ):
            raise TypeError("Missing polygon identities must be an immutable UUID tuple.")
        resolved_uuids = tuple(value.uuid for value in self.resolved)
        if len(set(resolved_uuids)) != len(resolved_uuids):
            raise ValueError("Resolved polygon identity UUIDs must be unique.")
        if len(set(self.missing)) != len(self.missing):
            raise ValueError("Missing polygon identity UUIDs must be unique.")
        if set(resolved_uuids) & set(self.missing):
            raise ValueError("Resolved and missing polygon identity UUIDs must be disjoint.")


class PolygonIdentityPort(Protocol):
    async def resolve(
        self, session: AsyncSession, request: PolygonIdentityRequest
    ) -> PolygonIdentityResult: ...


@dataclass(frozen=True, slots=True)
class OsmPostprocessingCompleted:
    """Öffentliches Ereignis nach atomar erfolgreicher OSM-Nachverarbeitung."""

    sequence: int | None
    osm_timestamp: datetime
    inserted: int
    updated: int
    deleted: int
    event_name: ClassVar[str] = OSM_POSTPROCESSING_COMPLETED_EVENT
    event_version: ClassVar[int] = OSM_POSTPROCESSING_COMPLETED_EVENT_VERSION

    def __post_init__(self) -> None:
        if self.sequence is not None and (type(self.sequence) is not int or self.sequence < 0):
            raise ValueError("OSM replication sequences must be non-negative integers.")
        if self.osm_timestamp.tzinfo is None or self.osm_timestamp.utcoffset() is None:
            raise ValueError("OSM timestamps must include a timezone.")
        if any(
            type(value) is not int or value < 0
            for value in (self.inserted, self.updated, self.deleted)
        ):
            raise ValueError("OSM reconciliation counts must be non-negative integers.")

    def to_payload(self) -> dict[str, JsonValue]:
        return {
            "sequence": self.sequence,
            "osm_timestamp": self.osm_timestamp.isoformat(),
            "inserted": self.inserted,
            "updated": self.updated,
            "deleted": self.deleted,
        }


@dataclass(frozen=True, slots=True)
class PermissionDefinition:
    """Module-owned metadata for one stable permission ID."""

    id: str
    module_id: str
    description: str
    category: str | None = None
    deprecated: bool = False
    replacement: str | None = None


class PermissionPort(Protocol):
    """Prüft eine stabile Permission-ID über die hostseitige Policy Engine."""

    async def is_allowed(
        self,
        permission_id: str,
        *,
        principal_id: str | None,
        resource_id: str | None = None,
    ) -> bool: ...


@dataclass(frozen=True, slots=True)
class ModulePrincipal:
    """Minimale, fachneutrale Identität einer authentifizierten Request-Person."""

    id: str


type ModulePrincipalDependency = Callable[..., Awaitable[ModulePrincipal]]


class PermissionDependencyFactory(Protocol):
    """Erzeugt Host-authentifizierte FastAPI-Dependencies für Modulrouten."""

    def require(
        self,
        permission_id: str,
        *,
        csrf: bool = False,
    ) -> ModulePrincipalDependency: ...


class CachePort(Protocol):
    """Modulgebundener Byte-Cache mit TTL in positiven ganzen Sekunden."""

    async def get(self, key: str) -> bytes | None: ...

    async def set(self, key: str, value: bytes, *, ttl_seconds: int) -> bool: ...

    async def delete(self, *keys: str) -> int: ...

    async def clear(self) -> int: ...


class CacheGenerationPort(Protocol):
    """Versioniert geteilte Lesemodelle in der Transaktion des Aufrufers."""

    async def current(self, session: AsyncSession, resource: str) -> int: ...

    async def bump(
        self, session: AsyncSession, resources: Sequence[str]
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class PublicQueryLimits:
    """Unveränderliche Limits für öffentliche, potentiell teure Modulabfragen."""

    max_response_items: int
    cache_debug_headers: bool = False

    def __post_init__(self) -> None:
        if type(self.max_response_items) is not int or self.max_response_items < 1:
            raise ValueError("Public query response limits must be positive integers.")
        if type(self.cache_debug_headers) is not bool:
            raise TypeError("The cache debug header flag must be a boolean.")


class PublicQueryPort(Protocol):
    """Wendet Host-eigene Rate- und Statement-Timeout-Regeln an."""

    @property
    def limits(self) -> PublicQueryLimits: ...

    async def guard(
        self, request: Request, session: AsyncSession, resource: str
    ) -> None: ...

    def is_timeout(self, error: BaseException) -> bool: ...


@dataclass(frozen=True, slots=True)
class MapPreviewRequest:
    """Technologieneutrale Eingabe für eine öffentliche Kartenvorschau."""

    slug: str
    updated_at: datetime
    geometry: Mapping[str, object]
    bbox: tuple[float, float, float, float]
    width: int
    height: int
    category: str | None = None
    feature_kind: str = "area"


@dataclass(frozen=True, slots=True)
class MapPreviewResult:
    """Gerenderte Bytes mit stabilen HTTP-Validierungsmetadaten."""

    body: bytes
    content_type: str
    etag: str
    cache_hit: bool = False


class MapPreviewUnavailableError(RuntimeError):
    """Eine gültige Vorschauanfrage konnte nicht gerendert werden."""


class MapPreviewPort(Protocol):
    """Rendert Vorschauen ohne Renderer-, Dateisystem- oder Cache-Interna."""

    async def render(self, request: MapPreviewRequest) -> MapPreviewResult: ...


@dataclass(frozen=True, slots=True)
class PolygonScope:
    """Fachneutrale Auswahl interner Polygon-IDs aus einer Modulrelation."""

    polygon_ids: tuple[int, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.polygon_ids, tuple):
            raise TypeError("Polygon scope IDs must be an immutable tuple.")
        if any(type(value) is not int or value < 1 for value in self.polygon_ids):
            raise ValueError("Polygon scope IDs must be positive integers.")
        if len(set(self.polygon_ids)) != len(self.polygon_ids):
            raise ValueError("Polygon scope IDs must be unique.")


@dataclass(frozen=True, slots=True)
class PolygonFilterValues:
    """Öffentliche Polygonfilter aus stabilen primitiven Werten."""

    categories: tuple[str, ...] = ()
    floors: tuple[str, ...] = ()
    area_sizes: tuple[str, ...] = ()
    occupancy_statuses: tuple[str, ...] = ()
    business_structures: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CountValue:
    """Ein stabiler Schlüssel mit Anzahl und optionaler Beschriftung."""

    key: str
    count: int
    label: str | None = None


@dataclass(frozen=True, slots=True)
class CompletenessValue:
    """Vollständigkeit eines Polygonattributs in einem Aggregat."""

    key: str
    label: str
    complete: int
    total: int
    percent: float | None = None


@dataclass(frozen=True, slots=True)
class PolygonMetrics:
    """Öffentliches Aggregat der Polygon-/Analytics-Domäne."""

    polygon_count: int
    occupied_count: int
    vacant_count: int
    chain_count: int
    independent_count: int
    known_occupancy_count: int
    known_business_structure_count: int
    total_area_m2: float | None = None
    average_area_m2: float | None = None
    median_area_m2: float | None = None
    vacant_area_m2: float | None = None
    vacancy_area_rate: float | None = None
    vacancy_rate: float | None = None
    chain_store_rate: float | None = None
    data_updated_at: datetime | None = None
    size_distribution: tuple[CountValue, ...] = ()
    floor_distribution: tuple[CountValue, ...] = ()
    status_distribution: tuple[CountValue, ...] = ()
    business_structure_distribution: tuple[CountValue, ...] = ()
    data_completeness: tuple[CompletenessValue, ...] = ()


@dataclass(frozen=True, slots=True)
class PublicPolygonSummary:
    """Schreibgeschützte Polygonprojektion, niemals eine Host-ORM-Instanz."""

    id: str
    slug: str
    name: str
    category: str
    occupancy_status: str
    floor: str | None = None
    address_display_name: str | None = None
    area_m2: float | None = None


class PolygonQueryPort(Protocol):
    """Liest öffentliche Polygonprojektionen für eine fachneutrale Auswahl."""

    async def list_by_scope(
        self, session: AsyncSession, scope: PolygonScope, *, limit: int
    ) -> tuple[PublicPolygonSummary, ...]: ...


class PolygonAnalyticsPort(Protocol):
    """Berechnet Polygon-Aggregate für eine fachneutrale Auswahl."""

    async def metrics(
        self,
        session: AsyncSession,
        scope: PolygonScope,
        filters: PolygonFilterValues,
    ) -> PolygonMetrics: ...

    async def category_counts(
        self,
        session: AsyncSession,
        scope: PolygonScope,
        filters: PolygonFilterValues,
    ) -> tuple[CountValue, ...]: ...


@dataclass(frozen=True, slots=True)
class StatisticsArea:
    id: UUID
    slug: str
    name: str
    area_type: str


@dataclass(frozen=True, slots=True)
class StatisticsSelection:
    """Vom aufrufenden Fachmodul vollständig aufgelöster Statistikbezug."""

    requested: StatisticsArea
    target: StatisticsArea
    municipality: StatisticsArea
    inherited: bool = False


@dataclass(frozen=True, slots=True)
class StatisticsSource:
    name: str
    url: str
    license: str
    source_updated_at: datetime | None
    last_import_at: datetime | None


@dataclass(frozen=True, slots=True)
class StatisticValue:
    key: str
    name: str
    category: str
    value: Decimal | None
    unit: str
    period: str
    period_start: date
    area_level: str
    is_calculated: bool
    municipality_value: Decimal | None = None
    difference: Decimal | None = None
    relative_difference: Decimal | None = None


@dataclass(frozen=True, slots=True)
class AreaStatistics:
    area: StatisticsArea
    statistics_area: StatisticsArea
    inherited_from_parent: bool
    source: StatisticsSource | None
    latest: tuple[StatisticValue, ...] = ()


@dataclass(frozen=True, slots=True)
class StatisticSeriesPoint:
    period: str
    period_start: date
    value: Decimal | None
    suppressed: bool


@dataclass(frozen=True, slots=True)
class AreaStatisticSeries:
    area: StatisticsArea
    statistics_area: StatisticsArea
    inherited_from_parent: bool
    source: StatisticsSource | None
    metric: Mapping[str, str]
    series: tuple[StatisticSeriesPoint, ...] = ()

    def __post_init__(self) -> None:
        _validate_string_mapping(self.metric, name="metric")
        object.__setattr__(self, "metric", MappingProxyType(dict(self.metric)))


class StatisticsQueryPort(Protocol):
    """Liest Kommunalstatistik für einen fachlich bereits aufgelösten Bezug."""

    async def for_selection(
        self, session: AsyncSession, selection: StatisticsSelection
    ) -> AreaStatistics | None: ...

    async def series_for_selection(
        self, session: AsyncSession, selection: StatisticsSelection, metric_key: str
    ) -> AreaStatisticSeries | None: ...


STATISTICS_QUERY_SERVICE_ID = "statistics.query"
STATISTICS_QUERY_SERVICE_VERSION = 1


class MetricsPort(Protocol):
    """Vendor-neutraler Zugriff auf begrenzte Modulmetriken."""

    def increment(
        self,
        name: str,
        *,
        value: float = 1,
        attributes: Mapping[str, str] | None = None,
    ) -> None: ...

    def observe(
        self,
        name: str,
        value: float,
        *,
        attributes: Mapping[str, str] | None = None,
    ) -> None: ...


class SpanPort(Protocol):
    """Kleiner, vendor-neutraler Trace-Span."""

    def set_attribute(self, name: str, value: str | float | bool) -> None: ...

    def record_exception(self, error: Exception) -> None: ...


class TracerPort(Protocol):
    """Erzeugt automatisch modulgebundene Trace-Spans."""

    def span(
        self,
        name: str,
        *,
        attributes: Mapping[str, str] | None = None,
    ) -> AbstractContextManager[SpanPort]: ...


class ObservabilityPort(Protocol):
    """Gebündelte, bereits an Modul-ID und Modulversion gebundene Telemetrie."""

    @property
    def logger(self) -> logging.LoggerAdapter: ...

    @property
    def metrics(self) -> MetricsPort: ...

    @property
    def tracer(self) -> TracerPort: ...


class StoragePort(Protocol):
    """Modulgebundener Blob-Storage ohne Dateisystem- oder Cloud-Annahmen."""

    async def read(self, key: str) -> bytes | None: ...

    async def write(self, key: str, value: bytes, *, content_type: str | None = None) -> None: ...

    async def delete(self, key: str) -> bool: ...

    async def exists(self, key: str) -> bool: ...


class HttpResponsePort(Protocol):
    """Begrenzte HTTP-Antwort ohne Zugriff auf den konkreten Client."""

    status_code: int
    headers: Mapping[str, str]
    content: bytes

    def json(self) -> object: ...


class HttpClientPort(Protocol):
    """Asynchroner HTTP-Port mit Host-kontrollierten Transport-Policies."""

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, str] | None = None,
        content: bytes | None = None,
    ) -> HttpResponsePort: ...


class HttpClientFactoryPort(Protocol):
    """Erzeugt einen sicheren Client; Timeouts und User-Agent besitzt der Host."""

    def create(
        self,
        *,
        service_name: str,
        base_url: str | None = None,
    ) -> AbstractAsyncContextManager[HttpClientPort]: ...


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Kleine, deterministische Retry-Policy für einen Joblauf."""

    max_attempts: int = 1
    initial_delay_seconds: float = 0
    backoff_multiplier: float = 2
    max_delay_seconds: float = 300

    def __post_init__(self) -> None:
        values = (
            self.initial_delay_seconds,
            self.backoff_multiplier,
            self.max_delay_seconds,
        )
        if type(self.max_attempts) is not int or self.max_attempts < 1:
            raise ValueError("Job retry max_attempts must be a positive integer.")
        if any(type(value) not in (int, float) or not math.isfinite(value) for value in values):
            raise ValueError("Job retry delays and multiplier must be finite numbers.")
        if self.initial_delay_seconds < 0 or self.max_delay_seconds < 0:
            raise ValueError("Job retry delays must not be negative.")
        if self.backoff_multiplier < 1:
            raise ValueError("Job retry backoff_multiplier must be at least one.")

    def delay_after(self, attempt: int) -> float:
        if type(attempt) is not int or attempt < 1:
            raise ValueError("Job retry attempts must be positive integers.")
        try:
            delay = self.initial_delay_seconds * self.backoff_multiplier ** (attempt - 1)
        except OverflowError:
            return self.max_delay_seconds
        return min(delay, self.max_delay_seconds)


@dataclass(frozen=True, slots=True)
class JobSchedule:
    """Technologieunabhängige V1-Anforderung für ein Ausführungsintervall."""

    interval_seconds: int

    def __post_init__(self) -> None:
        if type(self.interval_seconds) is not int or self.interval_seconds < 1:
            raise ValueError("Job schedule intervals must be positive integer seconds.")


@dataclass(frozen=True, slots=True)
class JobDefinition:
    """Öffentlicher, stabiler Job-Contract eines Moduls."""

    job_id: str
    handler: JobHandler
    retry: RetryPolicy = RetryPolicy()
    timeout_seconds: float | None = None
    schedule: JobSchedule | None = None
    allow_concurrent_runs: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.retry, RetryPolicy):
            raise TypeError("Job retry must be a RetryPolicy.")
        if self.schedule is not None and not isinstance(self.schedule, JobSchedule):
            raise TypeError("Job schedule must be a JobSchedule.")
        if (
            not (_JOB_NAME.fullmatch(self.job_id) or _EVENT_NAME.fullmatch(self.job_id))
            or len(self.job_id) > 160
        ):
            raise ValueError(
                "Jobs must use a local job name or the form <module-id>.<job-name>."
            )
        if not callable(self.handler):
            raise TypeError("Job handlers must be callable.")
        if self.timeout_seconds is not None and (
            type(self.timeout_seconds) not in (int, float)
            or not math.isfinite(self.timeout_seconds)
            or self.timeout_seconds <= 0
        ):
            raise ValueError("Job timeouts must be positive finite seconds.")
        if type(self.allow_concurrent_runs) is not bool:
            raise TypeError("allow_concurrent_runs must be a boolean.")


class SchedulerPort(Protocol):
    """Registriert Jobs ausschließlich im Namespace des gebundenen Moduls."""

    @overload
    def register(self, definition: JobDefinition) -> None: ...

    @overload
    def register(self, job_id: str, handler: LegacyJobHandler) -> None: ...


class ModuleSettingsPort(Protocol):
    """Liefert ausschließlich das validierte Settings-Modell des aktuellen Moduls."""

    @overload
    def get(self, settings_type: type[TSettings]) -> TSettings | None: ...

    @overload
    def get(self, key: str, default: T | None = None) -> object | T | None: ...

    @overload
    def require(self, settings_type: type[TSettings]) -> TSettings: ...

    @overload
    def require(self, key: str) -> object: ...


@dataclass(frozen=True, slots=True)
class ModuleContext:
    """Unveränderlicher, an genau ein Modul gebundener Host-Service-Context."""

    module_id: str
    module_version: str
    api: ApiRegistrar
    lifecycle: LifecycleRegistrar
    observability: ObservabilityPort
    database: DatabaseSessionProvider | None = None
    events: EventBusPort | None = None
    services: ServiceRegistryPort | None = None
    permissions: PermissionPort | None = None
    permission_dependencies: PermissionDependencyFactory | None = None
    cache: CachePort | None = None
    cache_generations: CacheGenerationPort | None = None
    public_queries: PublicQueryPort | None = None
    map_previews: MapPreviewPort | None = None
    polygons: PolygonQueryPort | None = None
    polygon_analytics: PolygonAnalyticsPort | None = None
    storage: StoragePort | None = None
    http: HttpClientFactoryPort | None = None
    scheduler: SchedulerPort | None = None
    settings: ModuleSettingsPort | None = None

    @property
    def logger(self) -> logging.LoggerAdapter:
        return self.observability.logger

    # Kompatibilitäts-Proxys für den kleinen Registration Context aus #94.
    def include_router(
        self,
        router: APIRouter,
        *,
        prefix: str = "",
        tags: Sequence[str] = (),
    ) -> None:
        self.api.include_router(router, prefix=prefix, tags=tags)

    def add_lifecycle(
        self,
        *,
        startup: ModuleLifecycleHook | None = None,
        shutdown: ModuleLifecycleHook | None = None,
    ) -> None:
        self.lifecycle.add_lifecycle(startup=startup, shutdown=shutdown)


class BackendModule(Protocol):
    """Öffentlicher Backend-Modulvertrag."""

    manifest: ModuleManifestV1

    def register(self, context: ModuleContext) -> None: ...


@dataclass(frozen=True, slots=True)
class ModuleDefinition:
    """Passive Discovery-Metadaten und verzögerte Modulinstanziierung."""

    manifest: ManifestInput | ModuleManifestV1
    loader: ModuleLoader
    origin: str
    declared_id: str
    persistence: ModulePersistenceContribution | None = None
    settings: ModuleSettingsContribution | None = None


__all__ = [
    "OSM_POSTPROCESSING_COMPLETED_EVENT",
    "OSM_POSTPROCESSING_COMPLETED_EVENT_VERSION",
    "OSM_SNAPSHOT_MAX_PAGE_SIZE",
    "OSM_SNAPSHOT_QUERY_SERVICE_ID",
    "OSM_SNAPSHOT_QUERY_SERVICE_VERSION",
    "POLYGON_IDENTITY_MAX_UUIDS",
    "POLYGON_IDENTITY_SERVICE_ID",
    "POLYGON_IDENTITY_SERVICE_VERSION",
    "POLYGON_SPATIAL_MATCH_MAX_AREAS",
    "POLYGON_SPATIAL_MATCH_SERVICE_ID",
    "POLYGON_SPATIAL_MATCH_SERVICE_VERSION",
    "STATISTICS_QUERY_SERVICE_ID",
    "STATISTICS_QUERY_SERVICE_VERSION",
    "ApiRegistrar",
    "AreaStatisticSeries",
    "AreaStatistics",
    "BackendModule",
    "CacheGenerationPort",
    "CachePort",
    "CompletenessValue",
    "CountValue",
    "DatabaseSessionProvider",
    "DomainEvent",
    "EventBusPort",
    "EventEnvelope",
    "EventHandler",
    "HttpClientFactoryPort",
    "HttpClientPort",
    "HttpResponsePort",
    "JobDefinition",
    "JobHandler",
    "JobSchedule",
    "JsonScalar",
    "JsonValue",
    "LegacyJobHandler",
    "LifecycleRegistrar",
    "MapPreviewPort",
    "MapPreviewRequest",
    "MapPreviewResult",
    "MapPreviewUnavailableError",
    "MetricsPort",
    "ModuleContext",
    "ModuleDefinition",
    "ModuleLifecycleHook",
    "ModuleManifestV1",
    "ModuleMigrationSource",
    "ModulePersistenceContribution",
    "ModulePrincipal",
    "ModulePrincipalDependency",
    "ModuleSettingsContribution",
    "ModuleSettingsPort",
    "ObservabilityPort",
    "OsmFeatureCursor",
    "OsmFeatureSnapshot",
    "OsmFeatureSnapshotPage",
    "OsmGeometryKind",
    "OsmPostprocessingCompleted",
    "OsmSnapshotQuery",
    "OsmSnapshotQueryPort",
    "OsmTagFilter",
    "OsmType",
    "PermissionDefinition",
    "PermissionDependencyFactory",
    "PermissionPort",
    "PolygonAnalyticsPort",
    "PolygonFilterValues",
    "PolygonIdentity",
    "PolygonIdentityPort",
    "PolygonIdentityRequest",
    "PolygonIdentityResult",
    "PolygonMetrics",
    "PolygonQueryPort",
    "PolygonScope",
    "PolygonSpatialArea",
    "PolygonSpatialMatch",
    "PolygonSpatialMatchPort",
    "PolygonSpatialMatchRequest",
    "PolygonSpatialMatchResult",
    "PublicPolygonSummary",
    "PublicQueryLimits",
    "PublicQueryPort",
    "RetryPolicy",
    "SchedulerPort",
    "SerializableDomainEvent",
    "ServiceRegistryPort",
    "SpanPort",
    "StatisticSeriesPoint",
    "StatisticValue",
    "StatisticsArea",
    "StatisticsQueryPort",
    "StatisticsSelection",
    "StatisticsSource",
    "StoragePort",
    "TracerPort",
    "event_envelope",
    "parse_manifest",
]
