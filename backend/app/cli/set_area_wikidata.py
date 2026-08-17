import argparse
import asyncio

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.analysis_area import AnalysisArea
from app.services.wikidata_enrichment import QID_RE, WikidataClient, WikidataEnrichmentService


async def resolve_area(session: AsyncSession, reference: str) -> AnalysisArea:
    area = await session.scalar(select(AnalysisArea).where(AnalysisArea.slug == reference))
    if area is not None:
        return area
    matches = list((await session.scalars(
        select(AnalysisArea).where(func.lower(AnalysisArea.name) == reference.casefold())
    )).all())
    if not matches:
        raise SystemExit(f"Gebiet nicht gefunden: {reference}")
    if len(matches) > 1:
        slugs = ", ".join(sorted(area.slug for area in matches))
        raise SystemExit(f"Gebietsname ist nicht eindeutig; vollständigen Slug verwenden: {slugs}")
    return matches[0]


async def run(reference: str, qid: str, allow_name_mismatch: bool = False) -> None:
    if not QID_RE.fullmatch(qid):
        raise SystemExit("Wikidata-ID muss dem Format Q123 entsprechen")
    async with AsyncSessionLocal() as session:
        area = await resolve_area(session, reference)
        entity = await WikidataClient().entity(qid)
        if entity is None:
            raise SystemExit(f"Wikidata-Entity existiert nicht: {qid}")
        candidate_names = {value.casefold() for value in (entity.label, *entity.aliases) if value}
        if area.name.casefold() not in candidate_names and not allow_name_mismatch:
            raise SystemExit(
                f"Name passt nicht: Gebiet {area.name!r}, Wikidata {entity.label!r}. "
                "Nur nach manueller Prüfung mit --allow-name-mismatch bestätigen."
            )
        await WikidataEnrichmentService.set_manual_match(session, area.id, qid, entity)
        print(
            f"Manuell bestätigt: {area.name} -> {qid}"
            + (f" -> de.wikipedia.org/wiki/{entity.wikipedia_title}" if entity.wikipedia_title else "")
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Wikidata-Zuordnung eines Gebiets bestätigen")
    parser.add_argument("area", help="Vollständiger Gebietsslug oder eindeutiger Gebietsname")
    parser.add_argument("qid", help="Wikidata-ID im Format Q123")
    parser.add_argument(
        "--allow-name-mismatch", action="store_true",
        help="Abweichendes Wikidata-Label nach manueller Prüfung zulassen",
    )
    args = parser.parse_args()
    asyncio.run(run(args.area, args.qid, args.allow_name_mismatch))
