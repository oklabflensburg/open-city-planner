# ADR: Map Runtime und Extension Registries

- Status: Angenommen
- Datum: 2026-08-26
- Entscheidung: [Issue #103](https://github.com/oklabflensburg/open-city-planner/issues/103)
- Grundlage: Issues #101/#102 und die ADRs zu Build-Time-Modulen und UI-Extension-Points
- Epic: [Issue #91](https://github.com/oklabflensburg/open-city-planner/issues/91)

## Kontext

`MapCanvas.vue` war mit 998 Zeilen gleichzeitig Vue-View, MapLibre-Lifecycle,
Source-/Layer-Aufbau, Interaktionsrouter, Selection-Renderer, OSM-Viewport-Loader,
Suchoverlay und Performance-Instrumentierung. Neue Kartenmodule hätten dadurch den
zentralen Host ändern müssen. #103 darf dennoch keine komplette OSM-, Polygon- oder
Analysis-Area-Migration auslösen.

Die Frontend-Module aus #101 sind lokale Nuxt Layers zur Build-Zeit. #102 besitzt
bereits genau eine UI-Contribution-Registry mit den Slots `map.controls`,
`map.bottomSheet` und `map.contextMenu`. Die Kartenplattform baut auf diesen
Verträgen auf; sie führt weder einen zweiten Modulhost noch eine zweite UI-Registry
ein.

## Entscheidung

`MapCanvas.vue` ist ein kleiner Renderer und Composition Root. Der Composable
`useMapCanvasHost` verbindet die fachneutrale `MapRuntime` vorübergehend mit den
bestehenden Fachstores. Dieser Legacy-Adapter hält das bisherige Verhalten stabil,
bis die Domänen in #108 und #137 eigene Beiträge liefern.

```text
Build-Time Frontend Module
  -> deklarative Source-/Layer-Definitionen
  -> versiegelter Build-Snapshot
  -> MapRuntime
       -> MapLifecycle
       -> LayerRegistry
       -> ControlRegistry
       -> InteractionRegistry -> FeatureQuery
       -> SelectionManager
       -> DrawManager -> TerraDrawAdapter
       -> FeatureInfoRegistry
       -> AnalysisRegistry
       -> MapTelemetry
  -> MapLibre
```

Die SDK-Version steigt additiv von `1.1.0` auf `1.2.0`.

## Definitionen und Runtime-Zustand

Modulmanifeste enthalten ausschließlich JSON-sichere `map.sources`- und
`map.layers`-Definitionen. Discovery bindet `moduleId` und deterministische
`moduleOrder`, validiert Ownership sowie Referenzen und versiegelt den Snapshot vor
dem Nuxt-Build. Es gibt keine JavaScript-Strings, Remote-Komponenten oder
URL-basierten Codeimporte.

Ausführbare lokale Controls, Interactions, Selection Presentations,
Feature-Info- und Analysis-Provider sind typisierte SDK-Contracts. Ihre Instanzen
gehören den Runtime-Registries und erhalten eine Unregister-Funktion. Definitionen
sind nach Bootstrap stabil; Attachment-Zustand kann bei Style-Wechsel, HMR und
Unmount neu aufgebaut oder entfernt werden.

## IDs und Ownership

Modulbeiträge verwenden global stabile IDs mit Owner-Präfix:

```text
<module-id>.<source-name>
<module-id>.<layer-name>
```

Duplikate, fremde Präfixe und Layer mit unbekannter Source sind strukturelle
Bootstrap-Fehler. `LayerRegistry` entfernt beim Owner-Cleanup zuerst Layer und dann
Sources. Der Pilot `host.search-results*` ist host-owned; die übrigen bestehenden
unnamespaceten Fachlayer bleiben bis zu ihrer Modulmigration im dokumentierten
Legacy-Adapter.

## Layer-Reihenfolge

Registrierungsreihenfolge ist keine Rendering-Regel. Gruppen und aufsteigende
Priorität bestimmen die Reihenfolge:

1. `analysis`
2. `osm-polygons`
3. `cityplanner-polygons`
4. `selection`
5. `poi-clusters`
6. `pois`
7. `labels`
8. `overlay`

Die Gruppen spiegeln `docs/map-layer-order.md`. Während der Strangler-Phase nutzt
die Registry feste Legacy-Anker, sodass Modulbeiträge und bestehende Layer gemeinsam
deterministisch bleiben. Ordering läuft beim ersten `load` und nach `style.load`,
nicht während `move`, `drag`, `render` oder `idle`.

## Lifecycle, Cleanup und HMR

`MapLifecycle` besitzt Create, Load-/Style-Ready, Resize und Destroy. MapLibre wird
erst im Client-Lifecycle dynamisch importiert. `ResizeObserver` und
`requestAnimationFrame` bündeln Layout-Änderungen. Runtime-Destroy detachiert
Interactions und Controls, zerstört Draw/Selection, entfernt Layer vor Sources und
ruft zuletzt `map.remove()` auf.

Ein erneutes Attach prüft MapLibre-Zustand und erzeugt keine doppelten Sources,
Layer, Controls oder Listener. Style-Recovery verwendet denselben versiegelten
Definitionssnapshot. Deaktivierte Build-Time-Module gelangen weder in den Snapshot
noch in den Nuxt-Build.

## MapContext und MapLibre Escape Hatch

Module erhalten standardmäßig eine kleine `MapFacade` mit Kamera- und
Projektionsprimitives, Feature Query, Selection, Draw und Telemetrie. Die rohe
MapLibre-Instanz ist ausdrücklich nicht `context.map`. Nur APIs, die noch nicht als
stabiler Host-Primitive vorliegen, dürfen `context.unsafeMapLibre()` verwenden.
Diese Nutzung ist sichtbar, reviewbar und muss bei einer SDK-Erweiterung wieder
entfernt werden. Module dürfen keine privaten Runtime-Dateien importieren.

## State Ownership

Während dieses Schritts bleiben Pinia-Stores die Source of Truth für bestehende
Polygon-, OSM-, Analysegebiets-, View- und Panelzustände. Die neue Runtime kopiert
diese Zustände nicht. `SelectionManager` ist der öffentliche Owner für künftig
modular registrierte Selections; der Legacy-Adapter delegiert weiterhin an
`useMapSelection`, bis die zugehörigen Domänen migriert werden. Terra Draw bleibt in
den vorhandenen Polygonkarten; `DrawManager` kapselt seine stabile Adaptergrenze,
ohne die Editierflows in #103 umzubauen.

## UI, Accessibility und SSR

Die vorhandene UI-Registry rendert die drei Map-Slots im host-owned Container.
`map.controls` verlangt ein `accessibleLabel`; Host-Focus-Styles, Tastaturzugang und
responsive Platzierung bleiben Host-Verantwortung. Keyboard-Interactions laufen
koordiniert über `InteractionRegistry`; der Map-Canvas erhält dafür bei Bedarf einen
Tabindex.

Der Snapshot ist server- und clientseitig identisch. MapLibre-, Worker-, CSS- und
Terra-Draw-Imports bleiben clientseitig. Das SDK selbst enthält keine Browseraktion
bei Import und bleibt im SSR-Build typisierbar.

## Performance und Fehler

`MapTelemetry` misst Map-Initialisierung, Style-Bereitschaft und Layer-Attachment
ohne Feature-IDs oder andere hoch-kardinale Labels. Der bestehende OSM-Pfad bleibt
auf `moveend`, Debounce, Abort, Coverage-Cache und Stale-Guard begrenzt. Es entstehen
keine neuen Arbeiten während aktivem Pan.

Strukturelle Definitionsfehler schlagen vor dem Build fehl. Runtimefehler verwenden
strukturierte Fehler (`MapRuntimeError`, Duplicate-/Unknown-/Sealed-Varianten und
`MapExtensionError`). Ein Attachmentfehler wird beobachtbar geloggt, ohne den
anschließenden Legacy-Kartenaufbau absichtlich zu blockieren.

## Folgen und Migration

Neue Module können eine Source und einen Layer ohne Änderung an `MapCanvas.vue`
beitragen. Der risikoarme Suchergebnis-Overlay ist der erste bestehende Layerpfad
über die Registry. OSM-Viewport-Laden, Polygonauswahl, Analysegebiete, Social Preview
und Terra-Draw-Flows bleiben verhaltensgleich im Legacy-Adapter.

Die verbleibende Fachorchestrierung im Adapter ist bewusste Folgearbeit, kein neues
Host-SDK. #108 migriert konkrete Fachbeiträge; #137 entfernt die entsprechenden
Legacy-Pfade nach Characterization-, E2E- und Performance-Nachweis.
