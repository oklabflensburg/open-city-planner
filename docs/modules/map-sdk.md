# Map Runtime und Map SDK

Issue #103 führt die fachneutrale Kartenplattform schrittweise ein. Vor dem
Refactoring lagen die folgenden Verantwortlichkeiten in
`frontend/app/components/map/MapCanvas.vue`:

| Verantwortung | Art | bisheriger State Owner | Ereignisse und Cleanup | Ziel |
| --- | --- | --- | --- | --- |
| MapLibre-Erzeugung, Style-Bereitschaft und Fehler | Host | lokale Map-Referenz, `mapStore.mapLoaded` | `load`, `style.load`, `error`, `map.remove()` | `MapLifecycle` |
| Resize und View-Zustand | Host | MapLibre und `mapStore` | `ResizeObserver`, Window-Events, `moveend` | `MapLifecycle` und `MapFacade` |
| Sources, Layer und Reihenfolge | gemischt | MapLibre | Style-Recovery; Layer vor Sources entfernen | `LayerRegistry`, zunächst Legacy-Adapter |
| Klick, Hover und Drag-Cursor | gemischt | lokale Hover-Refs und Stores | MapLibre-/Canvas-Listener | `InteractionRegistry`, zunächst Legacy-Adapter |
| Auswahl und Highlighting | gemischt | `mapStore` bleibt Source of Truth | Store-Watcher, Feature-State-Cleanup | `SelectionManager` als Adapter |
| Polygon-Zeichnen/-Editieren | fachlich | Terra Draw in den Polygonkarten | Terra-Draw-Events und Komponenten-Unmount | `DrawManager`-Contract; Migration folgt später |
| Feature-Details | fachlich | Polygon-, OSM- und Analysegebiet-Stores | Auswahlaktionen und Request-Cleanup der Stores | `FeatureInfoRegistry` |
| OSM-Viewport-Laden | fachlich | `osmViewport`-Store | `moveend`, Debounce, Abort und Stale-Guard | Legacy-Adapter bis zur OSM-Modulmigration |
| Suchergebnis-Overlay | fachlich klein | `mapStore.searchAction` | Store-Watcher, Source-Update | Pilot über `LayerRegistry` |
| Social Preview und Performance | Host/Adapter | lokale Zähler und Preview-Ref | `idle`, `moveend`, Window-Debug-Cleanup | Runtime-Telemetrie und Legacy-Adapter |

Die bestehenden Stores bleiben während dieses Strangler-Schritts die eindeutigen
Owner ihrer Fachzustände. Runtime-Manager duplizieren diesen Zustand nicht.

Die vollständige Entscheidung steht im
[Map-Runtime-ADR](../architecture/adr-map-runtime-and-extension-registries.md).
Die hier dokumentierten Legacy-Adapter
werden mit den Fachmigrationen aus #108 und #137 entfernt; sie sind kein zweiter
Modul- oder UI-Registry-Mechanismus.

## Source und Layer registrieren

Ein Frontend-Modul ergänzt seine bestehende `module.json` deklarativ:

```json
{
  "publicContributions": {
    "routes": [],
    "ui": [],
    "map": {
      "sources": [
        {
          "id": "mein-modul.orte",
          "source": {
            "type": "geojson",
            "data": { "type": "FeatureCollection", "features": [] }
          }
        }
      ],
      "layers": [
        {
          "id": "mein-modul.orte-punkte",
          "sourceId": "mein-modul.orte",
          "group": "overlay",
          "priority": 100,
          "layer": {
            "type": "circle",
            "paint": { "circle-color": "#154d73", "circle-radius": 6 }
          }
        }
      ]
    }
  }
}
```

IDs beginnen immer mit der Modul-ID. Die Layerdefinition enthält weder `id` noch
`source`; die Registry bindet beide kontrolliert. Kleinere Prioritäten liegen in
derselben Gruppe weiter unten. Die Gruppenreihenfolge ist im ADR festgelegt.

Das kanonische `reference`-Modul enthält ein ausführbares End-to-End-Beispiel mit
Source, Layer, Feature Info und sauberem Cleanup. Das kleinere `example-module`
bleibt eine interne Frontend-Contract-Fixture.

## Interaction und Cleanup

Lokale, bereits mitgebaute Integrationen verwenden die öffentlichen Typen aus
`#frontend-module-sdk`. Handler sind echte TypeScript-Funktionen und niemals Strings
im Manifest:

```ts
import type { MapInteractionContribution } from '#frontend-module-sdk'

const inspectPlaces: MapInteractionContribution = {
  id: 'mein-modul.orte-klick',
  moduleId: 'mein-modul',
  event: 'click',
  layerIds: ['mein-modul.orte-punkte'],
  priority: 100,
  handler(event) {
    if (!event.features?.length) return
    return { handled: true }
  }
}

const context = useMapContext()
const unregister = context.value?.interactions.register(inspectPlaces)
// beim Abbau des lokalen Beitrags:
unregister?.()
```

Module greifen auf den bereitgestellten `MapContext` über `useMapContext()` zu.
Kameraoperationen verwenden `context.value?.map`. Nur bei einer nachweislich
fehlenden Facade-Operation ist `context.value?.unsafeMapLibre()` zulässig.

Controls im bestehenden UI-Slot `map.controls` benötigen ein `accessibleLabel` und
bleiben per Tastatur erreichbar. Runtime-Registries entfernen beim Unregister und
Unmount ihre Listener, Controls, Layer und Sources; bei Sources werden zuerst alle
besitzenden Layer entfernt.
