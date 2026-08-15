# GIS-Kartenperformance

Stand: 14. August 2026

## Ergebnis

Der Redis-Hit war nicht der Engpass beim aktiven Verschieben. Das Profiling zeigte drei unabhängige Renderkosten:

1. Der bisherige VersaTiles-Stil `colorful` brachte 324 Basemap-Layer mit, davon 243 Linien- und 42 Symbol-Layer. Bei Zoom 15 waren 311 Basemap-Layer aktiv.
2. OSM-POIs wurden bei hohen Zoomstufen gleichzeitig als sichtbarer Kreis und als fast unsichtbare 16-Pixel-Hitbox gezeichnet. Das verdoppelte den Circle-Renderpass.
3. Gemeinde-, Stadtteil- und Quartiersgeometrien wurden gleichzeitig als Fill, Linie und Label gerendert, obwohl die Ebenen ineinander verschachtelt sind.

Die Netzwerk- und Vue-Seite war bereits besser als zunächst vermutet: Es gab keinen `move`-, `render`- oder `zoom`-Fetch. Viewportdaten wurden auf `moveend` geladen und der Kartenstand erst dort nach Pinia geschrieben. Der MapLibre-Renderpfad blieb dennoch teuer.

## Messmethode

Gemessen wurde in Chromium Headless mit SwiftShader-WebGL auf derselben Maschine, auf der Backend und Frontend liefen. Der Lauf simuliert drei Sekunden Dragging im Zentrum Flensburgs und erfasst:

- `requestAnimationFrame`-Abstände und Long Tasks
- Chromium `TaskDuration`, `ScriptDuration`, `LayoutDuration` und `RecalcStyleDuration`
- OSM-Requests und `setData()`-Aufrufe während des Drags
- Sources, Layer, Features, Vertices und geschätzten Client-Cacheverbrauch
- Desktop sowie 390×844 mit emulierten Touch-Events

Absolute FPS aus Headless/SwiftShader sind konservativ und nicht als Hardware-SLA zu verstehen. Die A/B-Vergleiche verwenden dieselbe Browser- und Maschinenkonfiguration. Der Lauf ist reproduzierbar:

```bash
google-chrome --headless=new --no-sandbox --enable-unsafe-swiftshader \
  --remote-debugging-port=9223 --user-data-dir=/tmp/stadtplaner-profile about:blank

cd frontend
PROFILE_URL=http://localhost:3000/ node scripts/profile-map.mjs
PROFILE_URL=http://localhost:3000/ PROFILE_MOBILE=true PROFILE_ZOOMS=15,17 node scripts/profile-map.mjs
PROFILE_URL=http://localhost:3000/ PROFILE_ZOOMS=19 PROFILE_ROUTE_CYCLES=10 node scripts/profile-map.mjs
```

`localhost` ist für den lokalen Lauf wichtig, da die lokale CORS-Konfiguration diesen Origin erlaubt.

## Basemap-Vergleich

Der neue lokale Stil `stadtplaner-light` enthält 24 Basemap-Layer. Davon sind bei Zoom 13 genau 17, bei Zoom 15 genau 21 und ab Zoom 17 alle 24 aktiv. Zum Vergleich: `colorful` enthält 324 und `neutrino` 207 Layer; bei Zoom 15 waren davon 311 beziehungsweise 201 aktiv.

Für den Vergleich wurden die Stadtplaner-Overlays ausgeblendet, damit nur die Basemap gerendert wird. Browser, Maschine, Viewport und Drei-Sekunden-Drag entsprechen dem bisherigen A/B-Lauf.

| Zoom | `colorful` FPS | `neutrino` FPS | `stadtplaner-light` FPS | Light vs. Colorful | Light vs. Neutrino |
|---:|---:|---:|---:|---:|---:|
| 13 | 20,2 | 20,7 | 21,9 | +8 % | +6 % |
| 15 | 18,0 | 22,0 | 28,7 | +59 % | +30 % |
| 17 | 19,9 | 27,9 | 34,9 | +75 % | +25 % |
| 19 | 23,6 | 29,8 | 39,8 | +69 % | +34 % |

Die MapLibre-Layerzahl beträgt jetzt 41 einschließlich der 17 Stadtplaner-Layer, gegenüber zuvor 342 mit `colorful` und 225 mit `neutrino`. Absolute SwiftShader-FPS schwanken zwischen Läufen; die Größenordnung der Layerreduktion und der Vorsprung bei hohen Zoomstufen sind der belastbare Befund.

Der lokale Stil nutzt nur 5 Symbol-, 10 Linien-, 8 Fill- und einen Background-Layer. Gebäude beginnen bei Zoom 15, kleine Wege und lokale Straßenlabels bei Zoom 16. Ein wichtiges Straßen-Casing existiert nur für Autobahn, Trunk und Hauptstraße. Basemap-Labels für Handel und Gastronomie sowie Sprite-Requests entfallen vollständig; Universität, Hochschule und Krankenhaus bleiben als wenige Orientierungspunkte erhalten.

## Browser- und Sichtprüfung

Der Stil wurde im echten MapLibre-Renderpfad bei Zoom 13, 15, 17 und 19 sowie in Desktop- und 390×844-Mobile-Viewports geladen. Alle verwendeten Source-Layer entsprechen dem Shortbread-Tileset; MapLibre meldete keine Style-, Source-Layer-, Tile- oder Glyph-Fehler. Die Screenshots zeigten:

- warme, nicht reinweiße Grund- und Gebäudeflächen,
- sichtbare, aber zurückhaltende Straßen- und Gebäudehierarchie,
- klare Stadtplaner-Flächen und farbige interaktive OSM-Punkte über der Basemap,
- lesbare Beschriftungen ohne doppelte Geschäfts- oder Gastro-POIs,
- keine Überdeckung der mobilen Kartenbedienung.

Mit allen Overlays erreichte der mobile Software-WebGL-Lauf bei Zoom 15 18,4 FPS und bei Zoom 17 23,8 FPS. Während beider Touch-Pans blieben OSM-Requests und `setData()`-Aufrufe bei null.

## Feature- und Payload-Messung

Die Backendantworten wurden mit denselben Flensburg-Viewports vor und nach der verschärften Zoom-Policy gezählt. Bytes sind unkomprimiertes JSON; Vertices wurden rekursiv aus den GeoJSON-Koordinaten gezählt.

| Zoom | Features vorher | Features nachher | Punkte / Polygone nachher | Bytes nachher | Vertices nachher |
|---:|---:|---:|---:|---:|---:|
| 13 | 1.200 | 800 | 800 / 0 | 287.342 | 800 |
| 15 | 1.800 | 1.200 | 1.000 / 200 | 557.939 | 7.283 |
| 17 | 1.038 | 1.038 | 928 / 110 | 489.145 | 6.885 |
| 19 | 194 | 194 | 184 / 10 | 73.273 | 379 |

Mit explizit aktivierten Gebäuden lieferte Zoom 17 insgesamt 1.188 Features: 928 Punkte, 110 sonstige Polygone und maximal 150 Gebäude bei 8.217 Vertices. Gebäude bleiben standardmäßig aus und werden unter Zoom 17 serverseitig ausgeschlossen.

Die Quoten sind getrennt: maximal 1.500 Punkte, 350 sonstige Polygone und 150 Gebäude innerhalb des zoomabhängigen Gesamtbudgets. So können Punkte die Polygonquote nicht mehr vollständig verdrängen.

## Layer-Binärsuche

Ein Zwischenlauf bei Zoom 15 mit 1.059 OSM-Features und 6.041 Vertices ergab unter identischen Headless-Bedingungen:

| Szenario | FPS |
|---|---:|
| alle Layer | 9,8 |
| OSM-Layer verborgen | 15,2 |
| alle Stadtplaner-Layer verborgen | 24,7 |

Das Ausblenden nur der Stadtplaner-Flächen brachte dagegen keinen relevanten Gewinn. OSM-Picking und die gleichzeitig gezeichneten Verwaltungsgrenzen waren die relevanten benutzerdefinierten Layerkosten.

## Nachher-Matrix

Die folgende Messung enthält Basemap, Stadtplaner-Flächen, OSM und Analysegebiete. Die absolute Framerate bleibt durch SwiftShader limitiert; entscheidend sind die Interaktionszähler und die Aufteilung der Main-Thread-Zeit.

| Zoom | Features | Vertices | FPS | Scripting | Layout | Recalc Style | Requests während Drag | `setData()` während Drag |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 13 | 800 | 800 | 12,6 | 347,0 ms | 1,3 ms | 2,0 ms | 0 | 0 |
| 15 | 1.059 | 6.041 | 16,1 | 203,7 ms | 0 ms | 0,1 ms | 0 | 0 |
| 17 | 180 | 334 | 21,0 | 285,4 ms | 0 ms | 0,1 ms | 0 | 0 |
| 19 | 20 | 56 | 24,0 | 288,2 ms | 0 ms | 0,2 ms | 0 | 0 |

Die Task-Zeit war wesentlich höher als Scripting, Layout und Style-Recalculation zusammen. Das bestätigt, dass der verbleibende Engpass MapLibre/WebGL und nicht Vue-Reaktivität oder CSS-Layout ist.

Bei 390×844 wurden mit Touch-Events ebenfalls 0 Requests und 0 `setData()` während des aktiven Pans gemessen. Zoom 15 enthielt 786 Features/5.653 Vertices, Zoom 17 194 Features/379 Vertices. Die gemessenen FPS lagen bei 18,4 beziehungsweise 23,8 unter derselben Software-WebGL-Begrenzung.

## Ausschluss großer Peninsula-Overlays

Die lokale OSM-Relation `14658378` („Angeln“, `natural=peninsula`) enthielt als Polygon 4.648 Geometriepunkte und 96.940 Bytes reines GeoJSON. Da der Viewport-Pfad Geometrien nicht am Ausschnitt abschneidet, dominierte dieses einzelne Orientierungsobjekt kleine Antworten vollständig. Nach dem serverseitigen Ausschluss ergab derselbe `landuse`-Viewport:

| Zoom | Kennzahl | vorher | nachher | Reduktion |
|---:|---|---:|---:|---:|
| 15 | Features | 44 | 43 | 2 % |
| 15 | Geometriepunkte | 4.649 | 808 | 83 % |
| 15 | JSON-Bytes | 112.021 | 32.280 | 71 % |
| 17 | Features | 8 | 7 | 13 % |
| 17 | Geometriepunkte | 4.738 | 90 | 98 % |
| 17 | JSON-Bytes | 101.857 | 4.719 | 95 % |

Das Feature gelangt nicht mehr in den MapLibre-Render- oder Picking-Pfad. Die unabhängige VersaTiles-Landdarstellung bleibt unverändert, sodass kein kartografisches Loch entsteht.

## Datenfluss nach der Änderung

```text
Drag / Touchmove
  -> nur MapLibre-Kamerabewegung
  -> keine Pinia-View-Mutation
  -> kein Fetch, keine Analytics, kein setData

moveend
  -> Kartenstand einmalig speichern
  -> liegt der Viewport im 20-%-Puffer und im selben Zoom-Bucket?
       ja: nichts tun
       nein: genau ein abbrechbarer Request
  -> Response in nichtreaktiven 4er-LRU legen
  -> POI- und Polygon-Source jeweils einmal aktualisieren
```

Der LRU ist auf vier Viewports begrenzt. Die konservative Obergrenze der Buchhaltung beträgt bei 2.000 Features etwa 4 MiB serialisierte Nutzdaten; der reale JavaScript-Heap kann wegen Objekt-Overhead größer sein, wächst aber nicht unbegrenzt.

## Event-Listener-Audit

| Event | Handler | Aufgabe | Kosten während Pan |
|---|---|---|---|
| `load` | Infrastruktur und Initialdaten | Sources/Layers einmal anlegen | keine, nur Initialisierung |
| `style.load` | Infrastruktur wiederherstellen | nur nach Stylewechsel | keine im normalen Pan |
| `moveend` | View speichern und Refresh planen | ein kleiner Pinia-Write, Coverage-Test | nur nach Pan |
| `click` | gezieltes Picking | ausschließlich interaktive Layer | keine während Pan |
| `mouseenter`/`mouseleave` | Cursor | CSS-Cursor | gering |
| `mousemove` auf Stadtplaner-Fill | Hover-ID wechseln | höchstens zwei `setFeatureState` bei Featurewechsel | kein `setData`, keine Paint-Neukompilierung |
| `error`/WebGL-Kontext | Fehlermeldung | nur Fehlerfall | keine reguläre Kosten |

Es existieren keine Listener für `move`, `drag`, `zoom`, `render` oder `idle`, die Netzwerk, Analytics oder Vue-State während der Kamerabewegung aktualisieren. `idle` wird nur einmalig nach einem tatsächlichen Source-Update zur Messung verwendet.

## Source-Strategie

| Source | Ladestrategie | Update-Trigger | Limit / Zoomstrategie |
|---|---|---|---|
| VersaTiles | MapLibre Vector Tiles | MapLibre Tile-Lifecycle | lokales `stadtplaner-light`, 24 Layer, keine zusätzlichen Handels-/Gastro-POIs |
| `osm-pois` | gepufferter Viewport, 4er-LRU | `moveend` außerhalb Buffer oder Filterwechsel | 800/1.200/2.000 Gesamtbudget; Cluster bis Zoom 14 |
| `osm-polygons` | gleicher Viewport-Request | wie POIs | eigene Polygon-/Gebäudequote, Vereinfachung unter Zoom 17 |
| `analysis-areas` | einmalig statisches GeoJSON | erster Kartenaufbau | Gemeinde 7–10,5; Stadtteil 9,5–13,5; Quartier ab 11,5 |
| `overview-polygons` | einmalig, danach nur Filteränderung | fachlicher Filter oder CRUD-Reload | aktuell 42 Features |

OSM- und Analyseauswahl sowie Stadtplaner-Hover/Selection verwenden stabile IDs und MapLibre `feature-state`. POI-Klicks verwenden statt einer zweiten unsichtbaren Circle-Schicht eine auf 10 Pixel begrenzte Abfrage des sichtbaren POI-Layers.

## Map-Lifecycle und Speicher

Die MapLibre-Instanz liegt in `shallowRef` und wird zusätzlich mit `markRaw` gespeichert. OSM-, Analysegebiets- und Stadtplaner-Geometrien werden bei der Zuweisung ebenfalls `markRaw` behandelt. Die Karte wird beim Unmount mit `map.remove()` zerstört, Timer und AbortController werden beendet und Window-Listener entfernt.

Nach zehn SPA-Wechseln von der Karte zur Projektseite und zurück blieben genau eine Map und ein MapLibre-Canvas bestehen. Nach erzwungener Garbage Collection blieben Dokumente konstant bei 3, DOM-Nodes sanken von 1.348 auf 1.344. Event-Listener stiegen einmalig von 194 auf 205, aber identisch sowohl nach fünf als auch nach zehn Zyklen; es gab daher kein lineares Listenerwachstum.

## MVT-Entscheidung

GeoJSON bleibt für diesen Schritt bestehen.

Begründung:

- Die größten gemessenen Viewports sind nach der neuen Policy 287–558 KB unkomprimiertes JSON und höchstens 1.200 Features; GZip reduziert die Übertragung zusätzlich.
- Die Karte aktualisiert diese Collections nicht mehr während des Pans.
- Details und rohe OSM-Tags sind bereits aus dem Viewport-DTO entfernt und werden erst nach Klick geladen.
- Eine MVT-Migration müsste das bestehende POI-Clustering, Filterparameter, stabile Feature-IDs und die Detailauswahl korrekt nachbilden. Ein bloßer Formatwechsel ohne serverseitige Cluster-/Generalisierungsstrategie würde bei kleinen Zooms wieder Einzelpunkte rendern.

MVT ist der nächste Architekturpfad, falls ein Hardware-GPU-Profil nach diesen Änderungen weiterhin unzureichend ist oder reale Viewports dauerhaft deutlich über etwa 1 MB beziehungsweise mehrere Tausend Features wachsen. Dann sollte ein binärer Endpoint `GET /api/v1/osm/tiles/{z}/{x}/{y}.pbf` mit `ST_AsMVTGeom`, `ST_AsMVT` und Redis-Key `osm:mvt:<version>:<z>:<x>:<y>:<filter-hash>` umgesetzt werden. Das jetzige Profil rechtfertigt noch nicht den zusätzlichen Betriebs- und Clustering-Aufwand.

## Performance-Budget

Während aktivem Pan gelten dauerhaft:

- 0 OSM- und Analytics-Requests
- 0 `setData()`-Aufrufe
- 0 Viewport-Mutationen in Pinia
- keine vollständige GeoJSON-Filterung oder Deep Clones
- ausschließlich gezieltes Picking auf interaktiven Layern

Nach `moveend` ist innerhalb der geladenen Bounds weiterhin 0 Arbeit vorgesehen. Außerhalb der Bounds wird genau ein abbrechbarer Viewport-Request gestartet.
