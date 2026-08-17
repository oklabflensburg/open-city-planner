import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from app.models.polygon_osm_source import PolygonOsmSource
from app.models.user_polygon import UserPolygon
from app.schemas.geojson import PolygonGeometry, PolygonVerwaltungUpdate
from app.schemas.osm import OsmPolygonImportRequest
from app.services.osm_import import (
    CONTAINER_SQL,
    OsmImportGeometryRequired,
    OsmImportNotImportable,
    create_polygon_from_osm,
    map_osm_category,
    map_osm_floor,
)
from app.services.osm_occupancy import detect_osm_occupancy_status
from app.services.polygons import update_polygon_verwaltung


class MappingRows:
    def __init__(self, row: dict[str, object] | None) -> None:
        self.row = row

    def mappings(self) -> "MappingRows":
        return self

    def first(self) -> dict[str, object] | None:
        return self.row


POLYGON = {
    "type": "Polygon",
    "coordinates": [[[9.43, 54.78], [9.44, 54.78], [9.44, 54.79], [9.43, 54.78]]],
}


@pytest.fixture(autouse=True)
def disable_nominatim_enrichment(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.osm_import.enrich_polygon_address", AsyncMock(return_value=False)
    )
    monkeypatch.setattr(
        "app.services.osm_import.refresh_polygon_area_assignments", AsyncMock(return_value=0)
    )
    monkeypatch.setattr(
        "app.services.osm_import.bump_cache_versions", AsyncMock(return_value=None)
    )


def source(*, dimension: int, tags: dict[str, str], geometry: dict[str, object] | None = None):
    return {
        "osm_type": "way" if dimension == 2 else "node",
        "osm_id": 42,
        "tags": tags,
        "imported_at": datetime(2026, 8, 13, tzinfo=UTC),
        "dimension": dimension,
        "geometry": geometry or POLYGON,
    }


@pytest.mark.parametrize(
    ("tags", "status", "source_tag"),
    [
        ({"shop": "vacant"}, "VACANT", "shop=vacant"),
        ({"disused:shop": "clothes"}, "VACANT", "disused:shop=clothes"),
        ({"building": "retail", "disused": "yes"}, "VACANT", "disused=yes"),
        ({"man_made": "tower", "disused": "yes"}, "UNKNOWN", "disused=yes"),
        ({"abandoned:shop": "clothes"}, "UNKNOWN", "abandoned:shop=clothes"),
        ({"shop": "supermarket"}, "UNKNOWN", None),
    ],
)
def test_detect_osm_occupancy_status(tags, status, source_tag) -> None:
    result = detect_osm_occupancy_status(tags)
    assert result.status == status
    assert result.source_tag == source_tag


def test_category_and_floor_mapping_are_conservative() -> None:
    assert map_osm_category({"shop": "clothes"}) == "fashion"
    assert map_osm_category({"disused:shop": "clothes"}) == "fashion"
    assert map_osm_category({"amenity": "restaurant"}) == "gastronomy"
    assert map_osm_floor({"level": "0"}, None) == "EG"
    assert map_osm_floor({"building:levels": "4"}, None) is None


@pytest.mark.parametrize(
    ("tags", "category"),
    [
        ({"shop": "shoes"}, "fashion"),
        ({"shop": "supermarket"}, "food"),
        ({"shop": "mobile_phone"}, "electronics"),
        ({"shop": "interior_decoration"}, "furniture"),
        ({"shop": "garden_centre"}, "garden"),
        ({"shop": "department_store"}, "warehouse"),
        ({"amenity": "cafe"}, "gastronomy"),
        ({"shop": "hairdresser"}, "services"),
        ({"shop": "beauty"}, "services"),
        ({"shop": "florist"}, "garden"),
        ({"shop": "cosmetics"}, "food"),
        ({"office": "insurance"}, "services"),
    ],
)
def test_actual_flensburg_osm_tags_map_to_stadtplanner_categories(tags, category) -> None:
    assert map_osm_category(tags) == category


def test_import_schema_forbids_geometry_claims_and_management_fields() -> None:
    with pytest.raises(ValidationError):
        OsmPolygonImportRequest(osm_type="way", osm_id=42, owner_name="Not allowed")


@pytest.mark.asyncio
async def test_peninsula_cannot_be_imported_as_stadtplaner_polygon() -> None:
    session = AsyncMock()
    session.execute.return_value = MappingRows(
        source(dimension=2, tags={"name": "Angeln", "natural": "peninsula"})
    )

    with pytest.raises(OsmImportNotImportable):
        await create_polygon_from_osm(
            session, OsmPolygonImportRequest(osm_type="way", osm_id=42), uuid.uuid4()
        )

    session.add.assert_not_called()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_polygon_import_uses_authoritative_geometry_and_osm_vacancy(monkeypatch) -> None:
    session = AsyncMock()
    session.add = MagicMock()
    session.execute.side_effect = [
        MappingRows(source(dimension=2, tags={"name": "Leerstand", "shop": "vacant"})),
        MappingRows(None),
    ]
    session.add.side_effect = lambda model: setattr(model, "id", 7) if isinstance(model, UserPolygon) else None
    enqueue = AsyncMock(return_value=None)
    monkeypatch.setattr("app.services.osm_import.enqueue_polygon_adoption", enqueue)

    result = await create_polygon_from_osm(
        session,
        OsmPolygonImportRequest(osm_type="way", osm_id=42),
        uuid.uuid4(),
    )

    assert result.geometry_source == "osm_feature"
    assert result.occupancy_status == "VACANT"
    assert result.occupancy_source == "OSM"
    added = [call.args[0] for call in session.add.call_args_list]
    polygon = next(item for item in added if isinstance(item, UserPolygon))
    relation = next(item for item in added if isinstance(item, PolygonOsmSource))
    assert polygon.created_by_user_id is not None
    assert polygon.owner_name is None
    assert relation.osm_type == "way" and relation.osm_id == 42
    assert relation.osm_snapshot["shop"] == "vacant"
    enqueue.assert_awaited_once_with(session, polygon, osm_type="way", osm_id=42)
    assert session.commit.await_count == 2


@pytest.mark.asyncio
async def test_point_import_uses_best_containing_area() -> None:
    point = {"type": "Point", "coordinates": [9.435, 54.785]}
    session = AsyncMock()
    session.add = MagicMock()
    session.execute.side_effect = [
        MappingRows(source(dimension=0, tags={"name": "Laden", "shop": "clothes"}, geometry=point)),
        MappingRows({"osm_type": "way", "osm_id": 9, "tags": {"building": "yes"}, "geometry": POLYGON, "imported_at": datetime(2026, 8, 13, tzinfo=UTC)}),
        MappingRows(None),
    ]
    session.add.side_effect = lambda model: setattr(model, "id", 8) if isinstance(model, UserPolygon) else None

    result = await create_polygon_from_osm(
        session, OsmPolygonImportRequest(osm_type="node", osm_id=42), uuid.uuid4()
    )
    assert result.geometry_source == "containing_osm_area"
    relations = [call.args[0] for call in session.add.call_args_list if isinstance(call.args[0], PolygonOsmSource)]
    assert [(relation.osm_type, relation.osm_id, relation.is_primary) for relation in relations] == [
        ("node", 42, True), ("way", 9, False)
    ]
    assert "ST_Covers" in str(CONTAINER_SQL)
    assert "ST_Area(ST_Transform" in str(CONTAINER_SQL)
    assert "candidate.tags->>'natural' IS DISTINCT FROM 'peninsula'" in str(CONTAINER_SQL)


@pytest.mark.asyncio
async def test_point_without_area_requires_manual_geometry() -> None:
    point = {"type": "Point", "coordinates": [9.435, 54.785]}
    session = AsyncMock()
    session.add = MagicMock()
    session.execute.side_effect = [
        MappingRows(source(dimension=0, tags={"shop": "books"}, geometry=point)),
        MappingRows(None),
    ]
    with pytest.raises(OsmImportGeometryRequired):
        await create_polygon_from_osm(
            session, OsmPolygonImportRequest(osm_type="node", osm_id=42), uuid.uuid4()
        )
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_point_accepts_explicit_manual_area_without_buffer() -> None:
    point = {"type": "Point", "coordinates": [9.435, 54.785]}
    session = AsyncMock()
    session.add = MagicMock()
    session.execute.side_effect = [
        MappingRows(source(dimension=0, tags={"shop": "books"}, geometry=point)),
        MappingRows(None),
    ]
    session.add.side_effect = lambda model: setattr(model, "id", 9) if isinstance(model, UserPolygon) else None
    result = await create_polygon_from_osm(
        session,
        OsmPolygonImportRequest(
            osm_type="node", osm_id=42, geometry=PolygonGeometry(**POLYGON)
        ),
        uuid.uuid4(),
    )
    assert result.geometry_source == "manual"


@pytest.mark.asyncio
async def test_management_override_marks_occupancy_as_manual(monkeypatch) -> None:
    polygon = SimpleNamespace(
        uuid=uuid.uuid4(), updated_at=datetime.now(UTC), occupancy_status="VACANT",
        occupancy_source="OSM", occupancy_source_tag="shop=vacant",
        occupancy_source_updated_at=datetime(2026, 8, 13, tzinfo=UTC),
        updated_by_user_id=None,
    )
    session = AsyncMock()
    expected_result = object()
    monkeypatch.setattr(
        "app.services.polygons.polygon_verwaltung_detail",
        AsyncMock(return_value=expected_result),
    )
    result = await update_polygon_verwaltung(
        session, polygon, PolygonVerwaltungUpdate(occupancy_status="OCCUPIED"), uuid.uuid4()
    )
    assert result is expected_result
    assert polygon.occupancy_status == "OCCUPIED"
    assert polygon.occupancy_source == "MANUAL"
    assert polygon.occupancy_source_tag is None
