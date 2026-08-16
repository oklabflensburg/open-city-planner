import argparse
import asyncio

from app.db.session import AsyncSessionLocal
from app.services.analysis_areas import sync_osm_analysis_areas


async def run(name: str, publish_relevant_updates: bool) -> None:
    async with AsyncSessionLocal() as session:
        report = await sync_osm_analysis_areas(
            session, name, publish_relevant_updates=publish_relevant_updates
        )
    print(f"Gemeinde: {report.municipality} (admin_level={report.municipality_admin_level})")
    print(f"Erkannte Ebenen: Stadtteile={report.district_admin_level}, Quartiere={report.quarter_admin_level}")
    print("Importiert: " + ", ".join(f"{key}={value}" for key, value in report.counts.items()))
    print(f"Social-Outbox: {report.social_events} Ereignisse")
    for warning in report.warnings:
        print(f"WARNUNG: {warning}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OSM-Verwaltungsflächen in Stadtplaner synchronisieren")
    parser.add_argument("--municipality", default="Flensburg", help="OSM-Gemeindename")
    parser.add_argument(
        "--publish-relevant-updates",
        action="store_true",
        help="Neue Gebiete und fachlich relevante Änderungen in die Mastodon-Outbox stellen",
    )
    args = parser.parse_args()
    asyncio.run(run(args.municipality, args.publish_relevant_updates))
