import argparse
import asyncio

from app.db.session import AsyncSessionLocal
from app.services.wikidata_enrichment import WikidataEnrichmentService


async def run(force: bool) -> None:
    async with AsyncSessionLocal() as session:
        report = await WikidataEnrichmentService().sync(session, force=force)
    print(
        f"Geprüft={report.checked}, OSM-Wikidata={report.osm_wikidata}, "
        f"OSM-Wikipedia={report.osm_wikipedia}, Suche={report.search}, "
        f"nicht gefunden={report.not_found}, ungültig={report.invalid}, "
        f"uneindeutig={report.ambiguous}, Konflikte={report.conflicts}"
    )
    for error in report.errors:
        print(f"FEHLER: {error}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gebiete persistent mit Wikidata anreichern")
    parser.add_argument("--force", action="store_true", help="Stale-Prüfung ignorieren")
    asyncio.run(run(parser.parse_args().force))
