import asyncio

from app.db.session import AsyncSessionLocal
from app.schemas.geojson import PolygonCreate, PolygonGeometry
from app.services.polygons import create_polygon

SEED_POLYGONS = [
    ("Verkaufsfläche 1", "fashion", [[[9.4327, 54.7848], [9.4337, 54.7852], [9.4340, 54.7847], [9.4330, 54.7843], [9.4327, 54.7848]]]),
    ("Verkaufsfläche 2", "gastronomy", [[[9.4356, 54.7838], [9.4364, 54.7841], [9.4366, 54.7836], [9.4358, 54.7833], [9.4356, 54.7838]]]),
    ("Testfläche", "custom", [[[9.4341, 54.7855], [9.4348, 54.7858], [9.4350, 54.7854], [9.4343, 54.7851], [9.4341, 54.7855]]]),
]


async def main() -> None:
    async with AsyncSessionLocal() as session:
        for name, category, coordinates in SEED_POLYGONS:
            await create_polygon(
                session,
                PolygonCreate(
                    name=name,
                    category=category,
                    description="Seed-Datensatz Innenstadt Flensburg",
                    geometry=PolygonGeometry(type="Polygon", coordinates=coordinates),
                    properties={"source": "seed"},
                ),
            )


if __name__ == "__main__":
    asyncio.run(main())
