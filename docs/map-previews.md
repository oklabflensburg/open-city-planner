# Serverseitige Kartenvorschauen

Die Startseite verwendet dynamische WebP-Kartenvorschauen für öffentliche Flächen und Analysegebiete. Öffentliche Gebiets- und Flächendetailseiten verweisen in ihren serverseitigen OpenGraph- und Twitter-Metadaten auf dieselben FastAPI-Endpunkte mit 1200×630 Pixeln. Der Produktionsrenderer ist kein Browser: `stadtplaner-map-renderer.service` lädt MapLibre Native in einem isolierten Node.js-Prozess auf `127.0.0.1:3020`. FastAPI kennt MapLibre nicht, sondern spricht ausschließlich mit der internen `MapPreviewRenderer`-Schnittstelle.

## Technische Auswahl

Für den Deployment-Stack wurde im August 2026 der offizielle Node-Binding-Release `@maplibre/maplibre-gl-native` geprüft. Die aktuelle Upstream-Dokumentation nennt vorgebaute Pakete für Ubuntu 24.04 auf amd64/arm64 und unterstützt Node.js 22. Das entspricht dem produktiven Ubuntu-24.04-/Node-22-Stack. Stabil gewählt ist Version `6.4.1`; `6.5.0-pre.1` ist nur eine Vorabversion. Der Release stammt aus dem aktiv gepflegten offiziellen `maplibre-native`-Repository und steht unter BSD-2-Clause. Deshalb wird dieser Binding-Pfad eingesetzt. Das generische Linux-CLI benötigt laut Upstream im Headless-Betrieb Xvfb und wurde nicht als paralleler Produktionspfad eingeführt. Ungepflegte Mapbox-Forks, alte Community-Bindings und Builds von `main` werden nicht verwendet.

Das Paket ist in `frontend/package.json` exakt auf `6.4.1` festgelegt. `pnpm-lock.yaml` verifiziert es mit `sha512-eiJnCOIea2PrGmxZnocP61kEJO4IAhNS/yvkdNh+PR50qdR4khAGU/dBA0IV+uXEQCu33Fux//J1wOQ5srYVGQ==`. Der Install-Hook des Pakets lädt das offizielle ABI-127-Native-Archiv. Damit dieser zweite Download nicht allein dem Hook vertraut, legt die Runtime-Rolle dasselbe GitHub-Release-Artefakt einmal versioniert unter `/opt/stadtplaner/toolchains/map-renderer/6.4.1/` ab und prüft SHA-256: `d04c0ddf89387a20a9cff93b57443ce756d34529dd83dc434bde1031b128ee59` für x86_64 beziehungsweise `82fdf555198711908fb3362316148f38b13f1df054fb381d4ee864c1a9762767` für aarch64. Der Release-Preflight vergleicht das von pnpm installierte `mbgl.node` bytegenau mit diesem verifizierten Artefakt. Es wird nicht auf dem Produktionshost aus Source gebaut und bei identischen Deployments weder erneut entpackt noch gebaut.

Ansible verlangt Ubuntu 24.04 sowie x86_64 oder aarch64 und installiert nur die aus dem Native-Binary beziehungsweise dem Software-Rendering abgeleiteten Laufzeitpakete: `libcurl4t64`, `libgl1-mesa-dri`, `libglx0`, `libicu74`, `libjpeg-turbo8`, `libopengl0`, `libpng16-16t64`, `libuv1t64`, `libwebp7`, `libx11-6`, `libxext6`, `xauth`, `xvfb` und `zlib1g`. Ein expliziter Test ohne `DISPLAY` bestätigt, dass das offizielle Node-Binary einen X-Kontext benötigt. Die Unit folgt daher dem offiziellen MapLibre-Linux-Headless-Weg und startet den Worker mit `xvfb-run -a`; `-nolisten tcp` verhindert einen Netzwerklistener des virtuellen X-Servers. `LIBGL_ALWAYS_SOFTWARE=1` und `GALLIUM_DRIVER=llvmpipe` erzwingen weiterhin CPU-/Mesa-Rendering. Es gibt keine Desktop-Sitzung, keine physische GPU und kein festes `DISPLAY=:0`.

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

Der Cache-Schlüssel enthält `slug`, `updated_at`, den beim Release-Preflight berechneten SHA-256 des Styles, Breite und Höhe. Derselbe Wert wird als `MAP_PREVIEW_STYLE_HASH` an Renderer und FastAPI übergeben. Zulässig sind nur `320×180`, `640×360`, `800×450` und `1200×630`. Änderungen an Geometrie/Metadaten oder Style erzeugen deshalb ohne globale Löschoperation ein neues Objekt. FastAPI schreibt über eine `.partial`-Datei, `fsync` und atomisches Umbenennen. Der Renderer selbst besitzt keinen Schreibzugriff auf den Cache und keine Datenbank- oder Anwendungs-Secrets.

## Betrieb

## Release- und Deployment-Lifecycle

Die Rolle `stadtplaner_map_renderer` läuft nach der allgemeinen Runtime-Rolle und installiert ausschließlich Systembibliotheken sowie den eigenen Systembenutzer `stadtplaner-map-renderer` ohne Login oder Home. Der releaseabhängige Teil bleibt bewusst in der Rolle `stadtplaner`: Erst nach vollständigem Assembly unter `/opt/stadtplaner/releases/<sha>` validiert `preflight.mjs` als tatsächlicher Renderer-Benutzer den Style, Lockfile-Integrität und Native-Import. `ldd` darf keine fehlende Shared Library melden. Erst danach wird `/opt/stadtplaner/current` atomar umgeschaltet.

Die Unit startet Code, Taxonomie und `frontend/public/map-styles/stadtplaner-light.json` ausschließlich über diesen aktiven Symlink. Der Renderer leitet die Release-SHA aus dem aufgelösten `/opt/stadtplaner/current`-Ziel ab und berechnet die Style-SHA aus den tatsächlich gelesenen Bytes; FastAPI berechnet seinen Cache-Wert aus derselben aktiven Datei. Dadurch bleiben beide Werte auch nach einem Rollback korrekt, statt als statische Unit-Werte am fehlgeschlagenen Zielrelease zu hängen. Readiness wird nur grün, wenn ein kontrolliertes Fixture tatsächlich durch MapLibre Native gerendert und als WebP encodiert wurde. Ansible vergleicht Renderer-Version, Release-SHA und Style-SHA mit dem Zielrelease, lädt zusätzlich das Smoke-WebP und prüft danach denselben Kommunikationspfad durch FastAPI. Bei einem Fehler schaltet der Rescue-Block den Symlink zurück, startet API, Frontend und – sofern im vorherigen Release vorhanden – Renderer neu und prüft den vorherigen Release-Stand. Beim erstmaligen Einführen des Dienstes wird er im Rollback stattdessen sauber gestoppt. Dadurch können Code, Style und Backend nicht aus verschiedenen Releases stammen.

Relevante Einstellungen:

- Backend: `MAP_PREVIEW_RENDERER_URL`, `MAP_PREVIEW_RENDERER_TIMEOUT_SECONDS`, `MAP_PREVIEW_CACHE_DIR`, `MAP_PREVIEW_STYLE_PATH`
- Worker: `MAP_PREVIEW_HOST`, `MAP_PREVIEW_PORT`, `MAP_PREVIEW_STYLE_PATH`, `MAP_PREVIEW_STYLE_HASH`, `MAP_PREVIEW_MAX_CONCURRENT`, `STADTPLANER_RELEASE_SHA`

Der Worker bindet nur an Loopback, akzeptiert keine Style-, Tile-, Glyph- oder Dateisystem-URL aus Requests und begrenzt Payloadgröße sowie Parallelität auf standardmäßig zwei Renders. Überlast liefert kontrolliert HTTP 503. Die Unit liest keine Environmentdatei, nutzt `ProtectSystem=strict` und weitere systemd-Härtung und begrenzt CPU, Tasks und Speicher. FastAPI-Readiness hängt nach dem Deploy nicht vom Renderer ab; ein später nicht erreichbarer Worker führt nur bei Preview-Endpunkten zu HTTP 503.

Health-Endpunkte des internen Dienstes:

- `/health/live`: HTTP-Prozess läuft;
- `/health/ready`: Native-Engine, Style und echter Fixture-Render sind bereit;
- `/health/info`: Renderer-Version, Release-SHA und Style-SHA;
- `/health/smoke.webp`: das kontrollierte Native-Smoke-Bild.

## Vorläufige Laufzeitmessung

Die lokale Workstation läuft mit Ubuntu 25.10. Für eine kompatible, nicht systemweit installierte Messung wurden deshalb die offiziellen Ubuntu-24.04-Bibliotheken `libicu74` und `libpng16-16t64` in ein temporäres Verzeichnis entpackt und per `LD_LIBRARY_PATH` verwendet. Mit Node.js 22 und MapLibre Native 6.4.1 ergaben sich bei Zugriff auf die produktiven VersaTiles-Ressourcen die folgenden Prozesswerte. Ein zusätzlicher Lauf ohne geerbtes `DISPLAY`, über einen isoliert entpackten `xvfb-run` mit `-nolisten tcp`, erreichte erfolgreich Native-Readiness und bestätigte den produktiven Headless-Pfad.

| Messung | Ergebnis |
| --- | ---: |
| Prozessstart bis erfolgreicher 320×180-Readiness-Render | 1,058 s |
| erster 800×450-Render | 0,828 s |
| zweiter 800×450-Render mit warmen Ressourcen | 0,445 s |
| 1200×630 nach Warmup | 0,412 s |
| Peak RSS nach diesen Renders | 229 MiB |
| Peak RSS bei zwei parallelen 1200×630-Renders | 237 MiB |

Das sind Entwicklungswerte, keine Messung auf dem Produktionshost. Die großzügigen Schutzgrenzen `MemoryHigh=1G`, `MemoryMax=1536M`, `CPUQuota=200%` und `TasksMax=128` verhindern einen ungebremsten Ausreißer, ohne die gemessene Last knapp einzuschnüren. Nach dem ersten Produktionsdeploy sollten Peak RSS und P95-Renderzeit erneut gemessen werden; die fachliche Parallelität bleibt bis dahin bei zwei.

## Diagnose

```bash
sudo systemctl status stadtplaner-map-renderer
sudo journalctl -u stadtplaner-map-renderer -o cat
curl --fail http://127.0.0.1:3020/health/live
curl --fail http://127.0.0.1:3020/health/ready
curl --fail http://127.0.0.1:3020/health/info
curl --fail --output /tmp/stadtplaner-render-smoke.webp http://127.0.0.1:3020/health/smoke.webp
file /tmp/stadtplaner-render-smoke.webp
curl --fail --output /tmp/stadtplaner-api-preview-smoke.webp http://127.0.0.1:8008/health/map-preview.webp
```

Im Deploylog erscheinen ohne Secrets Renderer-Version, Release-SHA, Style-SHA und Healthstatus. Vollständige GeoJSON-Geometrien, Cookies, Header und freie Nutzerdaten werden nicht protokolliert.

Der reguläre Produktionsdeploy bleibt der vorhandene Ansible-Aufruf mit einem exakten, bereits gegateten Commit:

```bash
cd deploy/ansible
ansible-playbook playbooks/deploy.yml \
  -e @~/stadtplaner-vault.yml \
  --ask-vault-pass \
  -e stadtplaner_deploy_ref=<commit-sha>
```

Playwright bleibt für bestehende Social-Screenshots und mögliche Referenztests verfügbar, ist aber weder Primär- noch Fallbackrenderer der öffentlichen Vorschau-API. Ein späterer Rendererwechsel erfolgt hinter `MapPreviewRenderer`, ohne die HTTP-API zu verändern.
