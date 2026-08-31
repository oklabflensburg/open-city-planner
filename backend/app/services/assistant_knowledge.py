import hashlib
import json
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from enum import StrEnum

from app.services.osm_canonical import GASTRONOMY_AMENITIES, SHOP_CATEGORIES
from app.services.search_catalog import CATEGORY_LABELS, SEARCH_CATALOG
from app.services.search_interpreter import normalize_search_text

KNOWLEDGE_RETRIEVAL_VERSION = "1"


class KnowledgeType(StrEnum):
    CATEGORY = "CATEGORY"
    METRIC = "METRIC"
    DATA_SOURCE = "DATA_SOURCE"
    AREA_TYPE = "AREA_TYPE"
    FILTER = "FILTER"
    OSM_RULE = "OSM_RULE"
    STATISTIC = "STATISTIC"
    CONCEPT = "CONCEPT"


class RetrievalConfidence(StrEnum):
    EXACT = "EXACT"
    HIGH = "HIGH"
    AMBIGUOUS = "AMBIGUOUS"
    NOT_FOUND = "NOT_FOUND"


@dataclass(frozen=True, slots=True)
class KnowledgeEntry:
    key: str
    type: KnowledgeType
    title: str
    aliases: tuple[str, ...]
    description: str
    source_type: str
    source_path: str
    canonical_value: str | None = None

    def public_dict(self, *, confidence: RetrievalConfidence | None = None) -> dict[str, object]:
        result: dict[str, object] = {
            "key": self.key,
            "type": self.type,
            "title": self.title,
            "description": self.description,
            "canonical_value": self.canonical_value,
            "source": {
                "type": self.source_type,
                "path": self.source_path,
            },
        }
        if confidence is not None:
            result["confidence"] = confidence
        return result


@dataclass(frozen=True, slots=True)
class KnowledgeMatch:
    entry: KnowledgeEntry
    confidence: RetrievalConfidence


def _entries() -> tuple[KnowledgeEntry, ...]:
    category_entries = tuple(
        KnowledgeEntry(
            key=f"category.{category}",
            type=KnowledgeType.CATEGORY,
            title=CATEGORY_LABELS[category],
            aliases=SEARCH_CATALOG.category_synonyms.get(category, (category,)),
            description=(
                "Zur Kategorie Gastronomie zählen in den lokalen OSM-Daten die Tags "
                + ", ".join(f"amenity={value}" for value in sorted(GASTRONOMY_AMENITIES))
                + ". Die Zuordnung folgt der kanonischen Mappinglogik des Stadtplaners."
                if category == "gastronomy"
                else (
                    f"Zur Kategorie {CATEGORY_LABELS[category]} zählen in den lokalen "
                    "OSM-Daten die shop-Werte "
                    + ", ".join(f"shop={value}" for value in sorted(SHOP_CATEGORIES[category]))
                    + ". Die Zuordnung folgt der kanonischen Mappinglogik des Stadtplaners."
                    if category in SHOP_CATEGORIES
                    else f"{CATEGORY_LABELS[category]} ist ein kanonischer Filterwert "
                    "des Stadtplaners. Die konkrete Zuordnung folgt ausschließlich der "
                    "vorhandenen OSM- und Flächenlogik."
                )
            ),
            source_type="CODE",
            source_path="backend/app/services/osm_canonical.py",
            canonical_value=category,
        )
        for category in SEARCH_CATALOG.categories
    )
    return category_entries + (
        KnowledgeEntry(
            "occupancy.VACANT", KnowledgeType.CONCEPT, "Leerstand",
            ("leerstand", "leer", "leerstehend", "ungenutzt", "unvermietet", "vacant"),
            "VACANT bezeichnet einen ausdrücklich als leerstehend erkannten Zustand. Bei OSM wird er nur aus den kontrollierten Lifecycle-Regeln wie shop=vacant, disused:shop oder disused=yes mit Gewerbekontext abgeleitet.",
            "DOCUMENTATION", "docs/osm-data.md", "VACANT",
        ),
        KnowledgeEntry(
            "occupancy.OCCUPIED", KnowledgeType.CONCEPT, "Belegt",
            ("belegt", "genutzt", "vermietet", "occupied"),
            "OCCUPIED bezeichnet eine als belegt gepflegte Stadtplaner-Fläche. Aus dem Fehlen von OSM-Leerstandstags wird dieser Zustand nicht automatisch abgeleitet.",
            "SCHEMA", "backend/app/schemas/polygon_filters.py", "OCCUPIED",
        ),
        KnowledgeEntry(
            "occupancy.UNKNOWN", KnowledgeType.CONCEPT, "Unbekannter Belegungsstatus",
            ("unknown", "unbekannt", "unklar", "keine angabe"),
            "UNKNOWN bedeutet, dass der Belegungsstatus nicht ausreichend bekannt ist. UNKNOWN ist ausdrücklich nicht mit OCCUPIED gleichzusetzen.",
            "CODE", "backend/app/services/osm_occupancy.py", "UNKNOWN",
        ),
        KnowledgeEntry(
            "area_type.MUNICIPALITY", KnowledgeType.AREA_TYPE, "Gemeinde",
            ("gemeinde", "gemeinden", "stadt", "kommune"),
            "MUNICIPALITY ist die kommunale Ebene der Analysis Areas.",
            "SCHEMA", "backend/app/schemas/search.py", "MUNICIPALITY",
        ),
        KnowledgeEntry(
            "area_type.DISTRICT", KnowledgeType.AREA_TYPE, "Stadtteil",
            ("stadtteil", "stadtteile", "bezirk"),
            "DISTRICT bezeichnet einen Stadtteil innerhalb der kommunalen Analysis Areas.",
            "SCHEMA", "backend/app/schemas/search.py", "DISTRICT",
        ),
        KnowledgeEntry(
            "area_type.QUARTER", KnowledgeType.AREA_TYPE, "Quartier",
            ("quartier", "quartiere", "viertel", "stadtviertel"),
            "QUARTER bezeichnet die kleinräumige Quartiersebene unterhalb eines Stadtteils.",
            "SCHEMA", "backend/app/schemas/search.py", "QUARTER",
        ),
        KnowledgeEntry(
            "data_source.OSM", KnowledgeType.DATA_SOURCE, "OpenStreetMap",
            ("osm", "openstreetmap", "open street map"),
            "OpenStreetMap ist eine gemeinschaftlich gepflegte Geodatenquelle. Der Stadtplaner nutzt einen lokal importierten, kontrolliert kategorisierten Datenbestand.",
            "DOCUMENTATION", "docs/osm-data.md", "OSM",
        ),
        KnowledgeEntry(
            "data_source.STADTPLANNER", KnowledgeType.DATA_SOURCE, "Stadtplaner-Daten",
            ("stadtplaner", "stadtplaner daten", "gepflegte flächen", "gepflegte flaechen"),
            "Stadtplaner-Daten sind die im Projekt gepflegten öffentlichen Verkaufsflächen. Sie werden getrennt von lokalen OSM-Referenzobjekten ausgewertet.",
            "SCHEMA", "backend/app/schemas/polygon_filters.py", "STADTPLANNER",
        ),
        KnowledgeEntry(
            "data_source.STATISTICS", KnowledgeType.DATA_SOURCE, "Kommunale Statistik",
            ("kommunale statistik", "statistikquelle", "zahlenspiegel", "statistische daten"),
            "Die kommunalen Kennzahlen werden versioniert mit Quelle, Bezugszeitraum und Gebietsebene gespeichert. Für Stadtteile oder Quartiere kann transparent ein Wert des übergeordneten Gebiets verwendet werden.",
            "DOCUMENTATION", "docs/flensburg-statistics.md", "STATISTICS",
        ),
        KnowledgeEntry(
            "concept.intelligent_search", KnowledgeType.CONCEPT, "Intelligente Suche",
            ("intelligente suche", "suchlogik", "kartensuche", "wie funktioniert die suche"),
            "Die intelligente Suche übersetzt Fragen und Kartenbefehle in validierte, ausschließlich lesende Stadtplaner-Operationen. Zahlen und Kartenobjekte stammen aus den bestehenden Fachservices.",
            "DOCUMENTATION", "docs/intelligent-search.md", None,
        ),
        KnowledgeEntry(
            "concept.stadtplaner_assistant", KnowledgeType.CONCEPT, "Stadtplaner-Assistent",
            ("assistant", "assistent", "stadtplaner assistent", "wissenskatalog"),
            "Der Stadtplaner-Assistent kombiniert höchstens vier freigegebene Datenoperationen und kontrollierte Wissenseinträge zu strukturierten Antworten mit Quellenangaben.",
            "DOCUMENTATION", "docs/stadtplaner-assistant.md", None,
        ),
        KnowledgeEntry(
            "statistic.population", KnowledgeType.STATISTIC, "Bevölkerung",
            ("bevölkerung", "bevoelkerung", "einwohner", "einwohnerzahl", "bevölkerungsentwicklung", "bevoelkerungsentwicklung"),
            "Die Kennzahl population enthält die veröffentlichten Bevölkerungsstände als Personen je Berichtsperiode. Die Zeitreihe stammt aus der kommunalen Statistik und wird nicht aus Kartenobjekten abgeleitet.",
            "DOCUMENTATION", "docs/flensburg-statistics.md", "population",
        ),
        KnowledgeEntry(
            "statistic.households", KnowledgeType.STATISTIC, "Haushalte",
            ("haushalte", "haushaltszahl", "haushaltsentwicklung", "anzahl haushalte"),
            "Die Kennzahl households enthält die veröffentlichten Haushaltszahlen je Berichtsperiode. Quelle, Gebietsebene und eine mögliche Vererbung werden zusammen mit den Werten ausgegeben.",
            "DOCUMENTATION", "docs/flensburg-statistics.md", "households",
        ),
        KnowledgeEntry(
            "metric.vacancy_rate", KnowledgeType.METRIC, "Leerstandsquote",
            ("leerstandsquote", "vacancy rate"),
            "Die Leerstandsquote ist der Anteil der als VACANT erfassten Flächen an allen Flächen mit bekanntem Belegungsstatus. UNKNOWN fließt nicht als belegt ein.",
            "CODE", "backend/app/services/analytics.py", "vacancy_rate",
        ),
        KnowledgeEntry(
            "metric.retail_area_density_m2_per_km2", KnowledgeType.METRIC,
            "Einzelhandelsflächendichte",
            ("einzelhandelsdichte", "einzelhandelsflächendichte", "retail area density", "retail_area_density_m2_per_km2"),
            "Die Einzelhandelsflächendichte setzt die erfasste Verkaufsfläche in Quadratmetern zur Gebietsfläche in Quadratkilometern ins Verhältnis.",
            "DOCUMENTATION", "docs/modules/analysis-areas-dependency-inventory.md", "retail_area_density_m2_per_km2",
        ),
        KnowledgeEntry(
            "metric.poi_count", KnowledgeType.METRIC, "POI-Anzahl",
            ("poi", "pois", "poi anzahl", "anzahl pois"),
            "Die POI-Anzahl zählt die im lokalen OSM-Datenbestand innerhalb der exakten Analysis-Area-Geometrie erfassten relevanten Objekte.",
            "DOCUMENTATION", "docs/modules/analysis-areas-dependency-inventory.md", "poi_count",
        ),
        KnowledgeEntry(
            "filter.floor.EG", KnowledgeType.FILTER, "Erdgeschoss",
            ("erdgeschoss", "eg"),
            "EG ist der kanonische Geschossfilter für Erdgeschossflächen.",
            "SCHEMA", "backend/app/schemas/polygon_filters.py", "EG",
        ),
        KnowledgeEntry(
            "filter.floor.UG", KnowledgeType.FILTER, "Untergeschoss",
            ("untergeschoss", "ug"),
            "UG ist der kanonische Geschossfilter für Untergeschossflächen.",
            "SCHEMA", "backend/app/schemas/polygon_filters.py", "UG",
        ),
        KnowledgeEntry(
            "filter.floor.OG", KnowledgeType.FILTER, "Obergeschoss",
            ("obergeschoss", "og"),
            "OG ist der kanonische Geschossfilter für Obergeschossflächen.",
            "SCHEMA", "backend/app/schemas/polygon_filters.py", "OG",
        ),
        KnowledgeEntry(
            "filter.business_structure.CHAIN", KnowledgeType.FILTER, "Filialbetrieb",
            ("kette", "filialist", "filialbetrieb"),
            "CHAIN ist der kanonische Filterwert für Filialbetriebe.",
            "SCHEMA", "backend/app/schemas/polygon_filters.py", "CHAIN",
        ),
        KnowledgeEntry(
            "filter.business_structure.INDEPENDENT", KnowledgeType.FILTER,
            "Inhabergeführter Betrieb",
            ("unabhängig", "unabhaengig", "inhabergeführt", "inhabergefuehrt", "einzelbetrieb"),
            "INDEPENDENT ist der kanonische Filterwert für unabhängige beziehungsweise inhabergeführte Betriebe.",
            "SCHEMA", "backend/app/schemas/polygon_filters.py", "INDEPENDENT",
        ),
    )


KNOWLEDGE_CATALOG = _entries()
KNOWLEDGE_BY_KEY = {entry.key.casefold(): entry for entry in KNOWLEDGE_CATALOG}
KNOWLEDGE_VERSION = hashlib.sha256(
    json.dumps([asdict(entry) for entry in KNOWLEDGE_CATALOG], ensure_ascii=False, sort_keys=True).encode()
).hexdigest()[:12]


def get_knowledge(key: str) -> KnowledgeEntry | None:
    return KNOWLEDGE_BY_KEY.get(key.casefold())


def retrieve_knowledge(query: str, limit: int = 5) -> list[KnowledgeMatch]:
    normalized = normalize_search_text(query)
    if not normalized:
        return []
    scored: list[tuple[float, KnowledgeEntry, RetrievalConfidence]] = []
    query_tokens = set(normalized.split())
    for entry in KNOWLEDGE_CATALOG:
        candidates = {
            normalize_search_text(entry.key), normalize_search_text(entry.title),
            *(normalize_search_text(alias) for alias in entry.aliases),
        }
        if normalized in candidates:
            scored.append((1000.0, entry, RetrievalConfidence.EXACT))
            continue
        contained = [candidate for candidate in candidates if candidate and candidate in normalized]
        if contained:
            scored.append((800.0 + max(map(len, contained)), entry, RetrievalConfidence.HIGH))
            continue
        token_overlap = max((len(query_tokens & set(candidate.split())) for candidate in candidates), default=0)
        similarity = max((SequenceMatcher(None, normalized, candidate).ratio() for candidate in candidates), default=0.0)
        if token_overlap or similarity >= 0.78:
            scored.append((token_overlap * 100 + similarity, entry, RetrievalConfidence.HIGH))
    scored.sort(key=lambda item: (-item[0], item[1].key))
    return [KnowledgeMatch(entry, confidence) for _, entry, confidence in scored[:limit]]


def public_datasets() -> list[dict[str, object]]:
    return [
        get_knowledge("data_source.STADTPLANNER").public_dict(),  # type: ignore[union-attr]
        get_knowledge("data_source.OSM").public_dict(),  # type: ignore[union-attr]
        {
            "key": "data_source.ANALYSIS_AREAS", "type": "DATA_SOURCE",
            "title": "Analysis Areas",
            "description": "Gemeinde-, Stadtteil- und Quartiersgeometrien für räumliche Auswertungen.",
            "source": {"type": "SCHEMA", "path": "backend/app/models/analysis_area.py"},
        },
        get_knowledge("data_source.STATISTICS").public_dict(),  # type: ignore[union-attr]
    ]
