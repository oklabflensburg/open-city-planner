"""Deterministische OSM-Daten für den POI-Query-E2E-Test."""

import asyncio

from geoalchemy2.elements import WKTElement

from app.db.session import AsyncSessionLocal
from app.models.osm_feature import OsmFeature


async def seed() -> None:
    async with AsyncSessionLocal() as session:
        session.add_all(
            [
                OsmFeature(
                    osm_type="node",
                    osm_id=216001,
                    geometry=WKTElement("POINT(9.435 54.783)", srid=4326),
                    tags={"name": "E2E Café", "amenity": "cafe"},
                ),
                OsmFeature(
                    osm_type="node",
                    osm_id=216002,
                    geometry=WKTElement("POINT(9.436 54.7835)", srid=4326),
                    tags={"name": "E2E Restaurant", "amenity": "restaurant"},
                ),
            ]
        )
        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed())
