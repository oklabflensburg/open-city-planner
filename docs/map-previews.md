# Serverseitige Kartenvorschauen

Die Startseite verwendet dynamische WebP-Kartenvorschauen für öffentliche Flächen und Analysegebiete. Der Produktionsrenderer ist kein Browser: `stadtplaner-map-preview.service` lädt MapLibre Native in einem isolierten Node.js-Prozess auf `127.0.0.1:3020`. FastAPI kennt MapLibre nicht, sondern spricht ausschließlich mit der internen `MapPreviewRenderer`-Schnittstelle.

## Technische Auswahl

Für den Deployment-Stack wurde im August 2026 der offizielle Node-Binding-Release `@maplibre/maplibre-gl-native` geprüft. Die MapLibre-Dokumentation nennt vorgebaute Pakete für Ubuntu 24.04 auf amd64/arm64 und Node.js 20, 22 und 24. Das entspricht dem produktiven Ubuntu-24.04-/Node-22-Stack. Der Release stammt aus dem aktiv gepflegten offiziellen `maplibre-native`-Repository. Deshalb wird dieser Binding-Pfad eingesetzt. Zusätzliche Rust-Bindings würden einen weiteren Build- und Toolchainpfad einführen und wurden nicht gewählt.

Die vorgebauten Native-Binaries sind distributionsgebunden. Entwicklungssysteme mit einer anderen ICU-Version können den Prozess daher möglicherweise nicht lokal starten; reine Kamera-/Style-Tests bleiben dort ausführbar. Produktion und CI für den vollständigen Render-Smoke-Test müssen Ubuntu 24.04 verwenden.

Quellen:

- [Offizielle Node-Bindings](https://github.com/maplibre/maplibre-native/blob/main/platform/node/README.md)
- [MapLibre Native unter Linux](https://maplibre.org/maplibre-native/docs/book/platforms/linux/)
- [MapLibre-Native-Releases](https://github.com/maplibre/maplibre-native/releases)

## Renderpfad

1. FastAPI lädt die öffentliche Geometrie, die PostGIS-BBox und `updated_at`.
2. Der Worker liest ausschließlich `frontend/public/map-styles/stadtplaner-light.json` und ergänzt in einer Kopie eine GeoJSON-Source sowie Fill-/Line-Layer. Branchenfarben stammen aus derselben JSON-Taxonomie wie das Frontend.
3. Aus der BBox berechnet der Worker einen Web-Mercator-Viewport mit größenabhängigem Padding.
4. Der Resource-Callback erlaubt nur die im Style verwendeten VersaTiles-Tiles und Glyphs über HTTPS.
5. MapLibre Native rastert RGBA; Sharp ergänzt die aus der Source-Attribution abgeleitete OSM-Nennung und encodiert WebP.
6. FastAPI speichert das Ergebnis atomar unter `MAP_PREVIEW_CACHE_DIR` und liefert es mit ETag aus.

Der Cache-Schlüssel enthält `slug`, `updated_at`, SHA-256 des Styles, Breite und Höhe. Zulässig sind nur `320×180`, `640×360`, `800×450` und `1200×630`. Änderungen an Geometrie/Metadaten oder Style erzeugen deshalb ohne globale Löschoperation ein neues Objekt.

## Betrieb

Relevante Einstellungen:

- Backend: `MAP_PREVIEW_RENDERER_URL`, `MAP_PREVIEW_RENDERER_TIMEOUT_SECONDS`, `MAP_PREVIEW_CACHE_DIR`, `MAP_PREVIEW_STYLE_PATH`
- Worker: `MAP_PREVIEW_HOST`, `MAP_PREVIEW_PORT`, `MAP_PREVIEW_STYLE_PATH`, `MAP_PREVIEW_MAX_CONCURRENT`

Der Worker bindet nur an Loopback, akzeptiert keine Style- oder Ressourcen-URL aus Requests und begrenzt Payloadgröße sowie Parallelität. Ansible prüft `/health` vor Abschluss eines Rollouts. Ein nicht erreichbarer Worker führt bei Preview-Endpunkten zu HTTP 503, nicht zum Ausfall anderer API-Routen.

Playwright bleibt für bestehende Social-Screenshots und mögliche Referenztests verfügbar, ist aber weder Primär- noch Fallbackrenderer der öffentlichen Vorschau-API. Ein späterer Rendererwechsel erfolgt hinter `MapPreviewRenderer`, ohne die HTTP-API zu verändern.
