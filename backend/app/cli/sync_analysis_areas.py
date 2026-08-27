import argparse
import asyncio

from app.db.session import AsyncSessionLocal
from app.modules.analysis_areas.application.legacy_sync import sync_osm_analysis_areas
from app.services.wikidata_enrichment import WikidataEnrichmentService


async def run(name: str, publish_relevant_updates: bool, enrich_wikidata: bool) -> None:
    async with AsyncSessionLocal() as session:
        report = await sync_osm_analysis_areas(
            session, name, publish_relevant_updates=publish_relevant_updates
        )
        wikidata_report = await WikidataEnrichmentService().sync(session) if enrich_wikidata else None
    print(f"Gemeinde: {report.municipality} (admin_level={report.municipality_admin_level})")
    print(f"Erkannte Ebenen: Stadtteile={report.district_admin_level}, Quartiere={report.quarter_admin_level}")
    print("Importiert: " + ", ".join(f"{key}={value}" for key, value in report.counts.items()))
    print(f"Social-Outbox: {report.social_events} Ereignisse")
    for warning in report.warnings:
        print(f"WARNUNG: {warning}")
    if wikidata_report:
        print(
            "Wikidata: "
            f"geprüft={wikidata_report.checked}, OSM-ID={wikidata_report.osm_wikidata}, "
            f"OSM-Wikipedia={wikidata_report.osm_wikipedia}, Suche={wikidata_report.search}, "
            f"nicht gefunden={wikidata_report.not_found}, ungültig={wikidata_report.invalid}, "
            f"uneindeutig={wikidata_report.ambiguous}, Konflikte={wikidata_report.conflicts}"
        )
        for error in wikidata_report.errors:
            print(f"WIKIDATA-FEHLER: {error}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OSM-Verwaltungsflächen in Stadtplaner synchronisieren")
    parser.add_argument("--municipality", default="Flensburg", help="OSM-Gemeindename")
    parser.add_argument(
        "--publish-relevant-updates",
        action="store_true",
        help="Neue Gebiete und fachlich relevante Änderungen in die Mastodon-Outbox stellen",
    )
    parser.add_argument(
        "--skip-wikidata", action="store_true",
        help="Persistente Wikidata-Anreicherung nach dem OSM-Sync überspringen",
    )
    args = parser.parse_args()
    asyncio.run(run(args.municipality, args.publish_relevant_updates, not args.skip_wikidata))
