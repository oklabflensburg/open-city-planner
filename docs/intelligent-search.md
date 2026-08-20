# Intelligente Suche

Die semantische Mehrschritt-Erweiterung mit Groq und kontrolliertem Knowledge Retrieval ist in [Stadtplaner-Assistent – Phase 3](stadtplaner-assistant.md) dokumentiert.

Die intelligente Suche übersetzt deutsche Kartenbefehle und Fragen in einen strikt
typisierten Suchplan. Der MVP funktioniert vollständig ohne Sprachmodell und ist
standardmäßig mit `AI_SEARCH_ENABLED=false` konfiguriert.

## Bedienoberfläche

Auf Desktop-Ansichten ist der Sucheinstieg oben in der linken Seitenleiste
angeordnet. Die Karte bleibt dadurch frei von einem breiten, zentrierten Overlay.
Sobald eine Antwort dargestellt werden muss, verbreitert sich die linke Spalte auf
bis zu 420 Pixel und zeigt dort die Reiter **Antwort** und **Verlauf**. Filter und
Assistant verwenden denselben Pinia-Filterzustand; eine leere Filterliste aus der
API bedeutet deshalb ausdrücklich „vollständige Auswahl“ und entfernt zuvor aktive
Einschränkungen.

Die API liefert mit `presentation_behavior` ein explizites Darstellungsverhalten:

- `KEEP_OPEN` lässt Fragen, Trefferlisten, Kennzahlen, Wissen, Rückfragen und Fehler
  sichtbar;
- `AUTO_CLOSE` schließt das Panel nach einfachen Karten- oder Filterbefehlen und
  zeigt für fünf Sekunden eine kompakte Bestätigung;
- `COLLAPSE` wird im aktuellen Layout wie eine kompakte Bestätigung behandelt.

Auf Mobilgeräten bleibt nur der kompakte Sucheinstieg über der Karte. Antworten
werden im bereits vorhandenen Bottom Sheet angezeigt. Dieses übernimmt Fokusfalle,
Escape-Behandlung, Scrollverhalten und sichere Abstände des bestehenden
Dialogmusters.

Kartenbewegungen verwenden die zentrale Funktion `getMapViewportPadding`. Sie
berücksichtigt Desktop-Seitenspalten, den mobilen Sucheinstieg und ein geöffnetes
Bottom Sheet. Weil die Desktop-Panels eigene Grid-Spalten belegen, wird ihre volle
Breite nicht noch einmal als MapLibre-Innenabstand abgezogen. Nach jedem
Layoutwechsel wird `map.resize()` im nächsten Animation Frame ausgeführt; erst
danach werden neue Suchergebnisse eingepasst. Die langlebige GeoJSON-Source
`search-results` wird dabei weiterverwendet und nicht pro Suche neu angelegt.

> Das Sprachmodell generiert niemals SQL. Es übersetzt Nutzereingaben ausschließlich
> in einen validierten SearchPlan.

## Architektur

```text
Nutzereingabe
  → regelbasierter Search Interpreter
  → Pydantic-validierter SearchPlan
  → deterministischer Read-only Search Executor
  → vorhandene öffentliche Services oder kontrollierte PostGIS-Abfrage
  → strukturierte Antwort und typisierte Map Action
```

Die bestehende OpenAPI und ihre Domainwerte sind die fachliche Referenz. Der
Executor verwendet insbesondere die vorhandenen Services für Analysegebiete,
Gebietsdetails, GeoJSON, Analytics und Gesamtstadtvergleiche. Nur für konkrete
Features exakt innerhalb eines Gebiets gibt es eine ergänzende statische
PostGIS-Abfrage. Sie verwendet die Gebiets-Bounding-Box als GiST-Vorfilter und
anschließend `ST_Covers` mit einem repräsentativen Punkt. Nutzereingaben werden
niemals als SQL, Tabellenname, Join, Sortierung oder SQL-Ausdruck eingesetzt.

## SearchPlan

Ein Suchplan enthält:

- einen der Intents `SHOW_AREA`, `SHOW_ANALYSIS_AREAS`, `SHOW_FEATURES`,
  `CHANGE_FILTERS`, `COUNT_FEATURES`, `ASK_ANALYTICS` oder `COMPARE_AREA`;
- optional ein eindeutig aufgelöstes Gebiet mit ID, Slug, Name und Gebietstyp;
- ausschließlich die bestehenden Filter `categories`, `floors`, `area_sizes`,
  `occupancy_statuses`, `business_structures` und `sources`;
- den getrennten Darstellungsfilter `ALL`, `POINTS_ONLY` oder `POLYGONS_ONLY`;
- eine typisierte Kartenaktion.

Fehlende Filterlisten bedeuten weiterhin „alle“. `NONE` übernimmt die vorhandene
Semantik „keine Treffer“ und darf nicht mit anderen Werten derselben Dimension
kombiniert werden. Das interne `__none__` kann durch natürliche Sprache nicht
erzeugt werden.

Kartenaktionen sind `NONE`, `FIT_AREA`, `SHOW_ANALYSIS_AREAS`,
`REPLACE_SEARCH_LAYER` und `UPDATE_FILTERS`. Das Frontend aktualisiert dafür die
vorhandenen Pinia-Filter und eine einzige langlebige MapLibre-GeoJSON-Source namens
`search-results`.

Vor jeder Assistant-Anfrage wird der Kontext aus den aktuell sichtbaren
Sidebar-Filtern aufgebaut. Eigenständige neue Fragen und Suchbefehle übernehmen
keine Filter aus einer früheren Assistant-Antwort. Nur erkennbare Folgefragen wie
„und wie viele …“, „davon …“ oder reine Filterbefehle wie „nur Leerstände“ bauen
bewusst auf der aktuellen Auswahl auf. Dadurch können beispielsweise
`gastronomy` und `VACANT` nicht unbemerkt in spätere unabhängige Suchen gelangen.

## Regelbasiert unterstützte Beispiele

| Eingabe | Ergebnis |
| --- | --- |
| `Zeige alle Stadtteile` | Gebiete vom Typ `DISTRICT` anzeigen |
| `Zeige alle Quartiere` | Gebiete vom Typ `QUARTER` anzeigen |
| `Zeige Gastronomieflächen in der Altstadt` | Kategorie `gastronomy`, nur Polygone, exakte Gebietsabgrenzung |
| `Alle Restaurants in der Altstadt` | Kategorie `gastronomy` im aufgelösten Gebiet |
| `Nur Leerstände` | `occupancy_statuses=[VACANT]` |
| `Nur belegte Flächen` | `occupancy_statuses=[OCCUPIED]` |
| `Nur OSM` / `Nur Stadtplaner` | entsprechende Quelle auswählen |
| `Nur Erdgeschoss` | `floors=[EG]` |
| `Nur Ketten` / `Nur inhabergeführt` | bestehende Betriebsform auswählen |
| `Wie viele POIs gibt es in der Altstadt?` | vorhandene Gebietsanalytics |
| `Wie groß ist die Altstadt?` | `area_m2` aus dem vorhandenen Gebietsdetail |
| `Vergleiche Altstadt mit der Gesamtstadt` | vorhandener Gebietsvergleich |

Gebietsnamen werden aus `analysis_areas` geladen. Die Auflösung priorisiert exakte
Namen, case-insensitive Namen und exakte Slugs. Eine konservative Übereinstimmung
innerhalb eines Satzes folgt nur bei einem eindeutigen Kandidaten. Unbekannte
Gebiete liefern HTTP 404, mehrdeutige Namen HTTP 409.

## API

`POST /api/v1/search/interpret` erzeugt und validiert nur den Plan; außer der
Gebietsauflösung wird keine Fachabfrage ausgeführt.

```json
{
  "query": "Zeige mir in der Altstadt alle Gastronomieflächen"
}
```

`POST /api/v1/search` interpretiert und führt den Plan aus. Die Antwort enthält
`query`, `plan`, einen deutschen Antworttext, `map_action`, `data` und `warnings`.
Konkrete Kartenresultate sind auf 200 Features begrenzt. Zählungen erfolgen als
Aggregation in PostgreSQL und laden kein GeoJSON zum Zählen.

## Sicherheitsmodell

Die Suche ist ausschließlich lesend. Der kleine `SearchCatalog` erlaubt nur
öffentliche Analysegebiete, Analytics, Statistik, öffentliche Flächen, öffentliche
OSM-Daten und Datenquellenstatus. Nicht angeboten werden `/admin`, `/auth`,
`/users`, `/notifications`, `/email` oder irgendeine Mutation.

Pydantic verbietet zusätzliche Felder und prüft jeden Filterwert gegen die
vorhandenen Domain-Allowlisten. Prompts zu Benutzer-, E-Mail-, Passwort-, Token-,
MFA- oder Sitzungsdaten sowie Mutations-/SQL-Injections werden vor einer
Gebietsabfrage abgewiesen. Die Endpoints verwenden den bestehenden öffentlichen
Rate Limiter und das bestehende PostgreSQL-Statement-Timeout. Es gibt keine
dynamische Tabellen- oder Operationsauswahl.

## Optionaler Groq-Provider

Die Phase-1-Suche bleibt deterministisch. Der Phase-3-Assistent verwendet für
komplexe verbleibende Formulierungen einen austauschbaren Groq-Provider mit
Pydantic-validiertem `AssistantPlan`. Die Konfiguration lautet:

```dotenv
AI_SEARCH_ENABLED=false
AI_SEARCH_PROVIDER=groq
AI_SEARCH_MODEL=
GROQ_API_KEY=
GROQ_BASE_URL=https://api.groq.com/openai/v1
```

Der API-Schlüssel stammt ausschließlich aus der Backend-Umgebung. Die vollständige
OpenAPI, GeoJSON, private Felder und Datenbankzugänge werden nicht an das Modell
übertragen. Bei deaktivierter KI oder Provider-Ausfall bleiben alle deterministischen
Suchbefehle verfügbar.

## Verhältnis zum semantischen Assistenten und bekannte Grenzen

Die Endpunkte dieser ersten, deterministischen Suchschicht bleiben aus
Kompatibilitätsgründen bestehen. Die aktuelle Oberfläche verwendet für
Mehrschrittfragen, kommunale Statistik, kontrolliertes Projektwissen,
Mehrgebietsvergleiche und ausgewählte Umgebungsanalysen den weiterführenden
[`POST /api/v1/assistant/query`](stadtplaner-assistant.md). Dort kann optional
Groq ausschließlich zur Sprachinterpretation eingesetzt werden; Zahlen und
Kartenergebnisse stammen weiterhin aus den validierten Stadtplaner-Werkzeugen.

- Freie Formulierungen außerhalb der deterministischen Regeln benötigen einen
  aktivierten und korrekt konfigurierten Sprachprovider oder führen zu einer
  kontrollierten Rückfrage beziehungsweise Nicht-unterstützt-Antwort.
- Mehrgebietsvergleiche bleiben auf höchstens vier Gebiete begrenzt.
- Umgebungsanalysen verwenden ausschließlich vorhandene öffentliche Flächen und
  einen validierten Radius von 100 bis 2.000 Metern.
- Größenwörter wie „klein“ oder „sehr groß“ werden nicht auf S/M/L/XL gemappt,
  weil das Projekt dafür bewusst keine erfundenen Quadratmetergrenzen verwendet.
- Der Search-Layer ist eine Ergebnisdarstellung; die normalen Viewport-Layer und
  deren zentrale Deduplizierung bleiben unverändert.
