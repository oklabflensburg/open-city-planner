# Öffentliche Frontend-Platform-Ports

Seit Frontend-SDK `1.3.0` stellt `#frontend-module-sdk` kleine, fachneutrale
Platform- und UI-Contracts für installierbare Nuxt-Layer bereit. Die Ports sind
Adapter auf die vorhandene Host-Runtime; sie erzeugen weder eine zweite Runtime
noch einen zweiten Router, Pinia-Root oder globalen Host-Kontext.

## API und Verhalten

| Export | Zweck | Lifecycle und SSR | Fehlerverhalten | Status |
| --- | --- | --- | --- | --- |
| `useModuleHttp()` / `ModuleHttpClient` | Requests relativ zur Host-API einschließlich Cookies, CSRF, Request-ID und bestehendem Refresh-Verhalten | im Nuxt-Setup auf Client und Server; Request-Cookies werden bei SSR weitergereicht | verwirft mit dem bestehenden typisierten API-Fehler; kein stiller Fallback | stabil ab 1.3 |
| `useMapFilterPort()` / `MapFilterPort` | aktive fachneutrale GIS-Filter als neue `URLSearchParams`-Instanz lesen | im Nuxt-/Pinia-Kontext; SSR-sicher und ohne Browser-Globals | fail-fast außerhalb des Nuxt-/Pinia-Kontexts | stabil ab 1.3 |
| `useMapSelectionPort()` / `MapSelectionPort` | Auswahl als stabile `{ type, id }`-Projektion lesen oder über die bestehende Host-Auswahllogik löschen | im Nuxt-/Pinia-Kontext; rein lesender Zugriff auf den Auswahlzustand ist SSR-sicher | fail-fast außerhalb des Nuxt-/Pinia-Kontexts; OSM-Features werden ohne interne Feature-Daten als `osm_type/osm_id` projiziert | stabil ab 1.3 |
| `useMapStylePort()` / `MapStylePort` | konfigurierten, validierten MapLibre-Stil mit bestehendem offenen Fallback laden | Composable selbst ist SSR-sicher; `load()` führt einen Fetch aus und wird für interaktive Karten clientseitig im Mount-Lifecycle aufgerufen | verwirft nach Fehlschlag von primärem Stil und Fallback mit den geprüften Ursachen | stabil ab 1.3 |
| `setMapCursor`, `mapCursorValue` | generische MapLibre-Präsentationshelfer für module-owned Karten | Import ist SSR-sicher; DOM-Zugriff erfolgt ausschließlich beim Aufruf von `setMapCursor` | Cursorzustände sind typisiert | stabil ab 1.3 |
| `OcpStatusBadge`, `OcpProviderIcon` aus `#frontend-module-sdk/ui` | bewusst öffentliche, kleine UI-Primitives des vorhandenen Designsystems | normale SSR-fähige Vue-Komponenten, kein eigener App- oder CSS-Root | ungültige Props fallen in der TypeScript-/Vue-Prüfung auf | stabil ab 1.3 |

Nuxt-Navigation (`NuxtLink`, `navigateTo`) genügt den untersuchten Consumern. Für
Notifications, Session/User, Locale und Dialoge bestand kein Consumer; dafür wurde
keine spekulative API ergänzt.

## Dependency migration für Analysis Areas

Inventargrundlage ist `ocp-module-analysis-areas` PR #2, Commit `776da22`, mit 16
Dateien unter `frontend/host-compatibility/`. Kategorie: A öffentliches SDK, B
Platform Service, C UI Primitive, D Map Port, E Navigation, F Notification, G
andere Fachdomäne, H Analysis-Areas-Fachlogik, I Presentation Helper.

| Module file | Alter privater Host-Zugriff (einschließlich Auto-Imports) | Klasse / Nutzung | Neuer oder vorhandener öffentlicher Contract | Ergebnis |
| --- | --- | --- | --- | --- |
| `AnalysisAreaCard.vue` | `useMapSelection`; `useAnalysisAreasStore` | D Auswahl löschen; H Modulstore | `useMapSelectionPort`; Store bleibt module-owned | in installierbaren Layer verschieben |
| `AnalysisAreaDetailMap.vue` | `~/types/geo`, `~/config/mapStyles`, `~/utils/mapCursor`, `useApi`, Runtime-Config; `navigateTo` | G Polygon-GeoJSON; B HTTP; D/I Kartenstil/Cursor; E Nuxt-Navigation | `useModuleHttp`, `useMapStylePort`, `setMapCursor`; GeoJSON-Typ aus `geojson`; vorhandenes Nuxt `navigateTo` | in installierbaren Layer verschieben; Polygon-Endpunkt bleibt fachfremder API-Consumer |
| `AreaExternalLinks.vue` | keine; nur module-owned Typ und Komponente | H | kein neuer Contract | in installierbaren Layer verschieben |
| `AreaStatistics.vue` | auto-importiertes `StatusBadge` | C | `OcpStatusBadge` | in installierbaren Layer verschieben |
| `ComparableList.vue` | `~/types/analytics`, `usePolygonApi` | G Polygon-/Comparison-Domain | kein Host-Contract; Typ, API und Komponente gehören zur Polygon-/Comparison-Domain | dokumentiert ausschließen |
| `DistributionCharts.vue` | `~/utils/chartTheme`, `useAnalyticsStore`, `Card` | G Analytics-Domain; I Chartdarstellung; C | kein Host-Contract; Chartkonfiguration und Darstellung mit der Analytics-Domain migrieren | dokumentiert ausschließen |
| `ExternalSourceLink.vue` | auto-importiertes `ProviderIcon` | C; ansonsten H/I | `OcpProviderIcon` und `ExternalProvider` | in installierbaren Layer verschieben |
| `FastFacts.vue` | `~/utils/metrics`, `useAnalyticsStore`, `useFilterStore`, `useOsmViewportStore`, `Card` | G Analytics/Filter/OSM; I; C | kein Analysis-Areas-Contract; Analytics-Domain besitzt Komponente und Darstellung | dokumentiert ausschließen |
| `FastFactsEditor.vue` | `~/types/analytics`, `useAnalyticsStore` | G administrative Analytics-Domain | kein Host-Contract | dokumentiert ausschließen |
| `IndustryChart.vue` | `~/utils/chartTheme`, `~/utils/industries`, `useMapStore`, `useAnalyticsStore`, `useOsmViewportStore`, `useFilterStore`, `Card` | G Analytics/OSM/Filter; D Highlight; I Chart | vorhandene SDK-Exports `getIndustryLabel`/`getIndustryColor`; kein Analysis-Areas-Contract für den fachfremden Rest | dokumentiert ausschließen |
| `LocationAnalysis.vue` | `~/types/analytics`, `usePolygonApi` | G Polygon-Domain | kein Host-Contract | dokumentiert ausschließen |
| `MarketBenchmarks.vue` | `~/types/analytics`, `useAnalyticsStore` | G Analytics-Domain | kein Host-Contract | dokumentiert ausschließen |
| `PolygonStatistics.vue` | `~/utils/industries`, `usePolygonStore`, `useMapStore`, `useMapSelection`, `PolygonOsmInfo` | G Polygon-/OSM-Domain; D Auswahl | vorhandener SDK-Export `getIndustryLabel`; `useMapSelectionPort` wäre für Lesen/Löschen der Auswahl generisch, macht die fachfremde Komponente aber nicht Analysis-Areas-owned | dokumentiert ausschließen |
| `RentTable.vue` | `useAnalyticsStore`, `Card` | G Analytics-Domain; C | kein Analysis-Areas-Contract; Datenzustand und Darstellung bleiben Analytics-owned | dokumentiert ausschließen |
| `ViewportOsmSummary.vue` | `~/utils/osmCategories`, `~/utils/industries`, `useOsmViewportStore`, `Card` | G OSM-Domain; I; C | vorhandener SDK-Export `getIndustryLabel`; OSM-Zustand und Darstellung bleiben OSM-owned | dokumentiert ausschließen |
| `analysisAreas.ts` | `~/stores/map`, `~/utils/gisFilters`, `useFilterStore`, `useApi` | H Modulzustand; D Auswahl; B Filter/HTTP | `useMapSelectionPort`, `useMapFilterPort`, `useModuleHttp` | vollständig module-owned in installierbaren Layer verschieben |

Damit können `AnalysisAreaCard.vue`, `AnalysisAreaDetailMap.vue`,
`AreaExternalLinks.vue`, `AreaStatistics.vue`, `ExternalSourceLink.vue` und
`analysisAreas.ts` nach Anpassung ihrer Importpfade aus `host-compatibility`
entfernt und paketiert werden. Die übrigen zehn Dateien sind keine
Analysis-Areas-Fachdateien: Sie werden im Modulrepo mit obiger Ownership-Begründung
aus dem temporären Verzeichnis entfernt, nicht in den Host verschoben und nicht
als Analysis-Areas-Code neu etikettiert.

## Paketgrenze und Guard

Installierbare Frontend-Module dürfen eigene relative Dateien,
`#frontend-module-sdk`, öffentliche Nuxt-Imports und deklarierte
Drittanbieter-Pakete importieren. `~/`, `@/`, Pfade mit `frontend-modules/` und
relative Ausbrüche aus dem eigenen Paket werden abgewiesen. Der gemeinsame
TypeScript-AST-Scanner erfasst statische Imports, Re-Exports, dynamische Imports
und `require()` auch in Vue-Scriptblöcken.

Der Guard läuft sowohl bei lokaler Discovery als auch nach dem sicheren Entpacken
eines gebauten Frontend-`.tgz` im Installer-Preflight. Dadurch wird nicht nur ein
separater Quellbaum geprüft, sondern genau der installierbare Paketinhalt.
