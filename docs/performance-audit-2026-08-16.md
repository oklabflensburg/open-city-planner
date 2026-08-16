# Lighthouse-/Performance-Audit vom 16.08.2026

## Messbedingungen

- Lighthouse 13.4.1, Mobile-Standardprofil, Headless Chromium 150
- lokaler Nuxt-Production-Build auf `http://127.0.0.1:3010/`
- lokales FastAPI auf `http://127.0.0.1:8010/api/v1`
- Live-Messung gegen `https://stadtplaner.oklabflensburg.de/`
- Development-Werte werden nicht als Performancevergleich verwendet.

Die lokale Ausgangsmessung wurde nach Korrektur der nur lokal falschen CORS-Origin wiederholt. Dadurch sind API- und Konsolenbefunde mit der Anwendung vergleichbar.

## Lighthouse vorher/nachher

| Messwert | Lokal vorher | Lokal nachher | Live vor Deployment |
| --- | ---: | ---: | ---: |
| Performance | 35 | 61 | 40 |
| Accessibility | 87 | 100 | 87 |
| Best Practices | 96 | 96 | 96 |
| SEO | 100 | 100 | 100 |
| FCP | 5,06 s | 2,38 s | 2,50 s |
| LCP | 5,06 s | 2,38 s | 5,17 s |
| TBT | 7.364 ms | 6.737 ms | 10.256 ms |
| CLS | 0 | 0 | 0 |
| Speed Index | 6,96 s | 5,28 s | 8,02 s |

Die Hauptursachen für den niedrigen Lighthouse-Performancewert waren:

1. MapLibre und die vollständige Karteninitialisierung: Der MapLibre-Chunk war roh ca. 1,03 MB groß und verursachte im Live-Lauf Tasks bis 2,21 s. Er bleibt der dominante TBT-Engpass.
2. Fehlende vorkomprimierte lokale Produktionsassets: Die lokale Ausgangsmessung übertrug 2,34 MB; danach waren es 0,87 MB.
3. Mobil unsichtbare Desktop-Sidebars wurden trotzdem erzeugt und hydriert. Gleichzeitig starteten Analytics und OAuth-Provider-Erkennung ohne sichtbaren Bedarf.
4. MapLibre-CSS lag mit ca. 140 KB Gesamt-CSS im renderkritischen globalen Bundle.
5. Das Logo war unoptimiert (106,5 KB), das zusätzlich geladene ICO 133,5 KB.
6. Die Live-Konfiguration überschreibt den vorgesehenen lokalen Stil derzeit mit VersaTiles `colorful`. Dadurch wird unter anderem ein ca. 199-KB-Sprite geladen. Der Build ignoriert diesen bekannten schweren Legacy-Wert jetzt und verwendet `stadtplaner-light`.

## LCP

Das konkrete LCP-Element war vorher und nachher der Ladehinweis `div.pointer-events-none > div.flex` mit dem Text „Karte wird geladen …“. Der Container ist bereits serverseitig vorhanden und behält seine feste Höhe; CLS bleibt 0. Lokal sank der LCP von 5,06 s auf 2,38 s. Im finalen Lauf lagen TTFB bei 23 ms und Element-Render-Delay bei 171 ms.

## JavaScript, CSS und Long Tasks

| Ressource | Vorher | Nachher |
| --- | ---: | ---: |
| JS-Transfer (alle `.js`-Requests) | 1.579 KB | 500 KB |
| CSS-Transfer | 153 KB | 33 KB |
| Gesamttransfer | 2.339 KB | 872 KB |
| MapLibre-Chunk roh / Brotli | 1.028 KB / nicht vorkomprimiert | 1.028 KB / 222 KB übertragen |
| MapLibre-CSS roh / Brotli | im globalen CSS | 83 KB / 10,7 KB, lazy |

Die drei größten Long Tasks:

| Vorher | Nachher |
| ---: | ---: |
| MapLibre 1.997 ms | MapLibre 1.707 ms |
| MapLibre 1.217 ms | MapLibre 1.665 ms |
| MapLibre 851 ms | MapLibre 740 ms |

Die Streuung einzelner Tasks ist bei Lighthouse hoch. TBT verbesserte sich im vergleichbaren Lauf nur um rund 9 %. Das Ziel `< 600 ms` ist mit automatisch initialisiertem MapLibre auf der emulierten Low-End-CPU noch nicht erreicht. Die Karte wurde nicht hinter einen künstlichen Klick oder nach das Messfenster verschoben. Für eine weitere große TBT-Reduktion sind ein grundsätzlicher leichterer Kartenrenderer beziehungsweise ein auf Nutzeraktivierung beruhender Produktmodus gesondert abzuwägen.

Admin-, Auditlog-, Profil-, Dokumentations- und Editorcode liegen weiterhin in eigenen Route-Chunks. Der Polygoneditor wird auf `/` nicht geladen. MapLibre selbst ist ein dynamischer Chunk; die Kartenkomponente wird nun als Nuxt-Lazy-Komponente bei Browser-Idle hydriert. MapLibre-CSS wird nur von Kartenkomponenten angefordert.

## MapLibre und Daten

- `stadtplaner-light`: 24 Layer, davon 21 bei Zoom 15, 5 Symbol-, 10 Linien- und 8 Fill-Layer; kein Sprite.
- Default bleibt lokal `/map-styles/stadtplaner-light.json`, technischer Fallback bleibt `neutrino`.
- Live war entgegen der Vorgabe noch `colorful` konfiguriert. Der nächste Build fällt bei genau diesem Legacy-Wert sicher auf den lokalen Stil zurück.
- MapLibre bleibt `markRaw`, die Instanz wird nicht tief reaktiv.
- `powerPreference` der Hauptkarte bleibt `high-performance`; `preserveDrawingBuffer` ist nicht aktiv.
- Hover-Feature-Picking ist jetzt auf höchstens einen `requestAnimationFrame`-Durchlauf begrenzt.
- Viewport-Daten werden weiter erst nach Map-Ready geladen; `moveend`-Debounce, Coverage-Cache, Featurelimits, `natural=peninsula`-Ausschluss und Layerreihenfolge bleiben unverändert.

Initiale API-Requests im finalen mobilen Lauf:

| Endpoint | Transfer / entpackt | Sofort benötigt |
| --- | ---: | --- |
| `/auth/session` | 0,5 / 0,1 KB | Auth-Anzeige; liefert für Gäste 401 |
| `/analysis-areas` | 4,1 / 24,4 KB | Kartenflächen |
| `/analysis-areas/geojson` | 58,2 / 219,3 KB | Gebietsgrenzen |
| `/polygons/overview` | 5,9 / 26,6 KB | Stadtplaner-Flächen |
| `/osm/features` | 15,7 / 130,8 KB | OSM-Viewport nach Map-Ready |

Der zuvor zusätzliche `/auth/refresh`-Request und die öffentliche OAuth-Provider-Abfrage entfallen. Die Analytics-Übersicht wird mobil erst beim Öffnen von „Analyse“ geladen. Die API-Antworten sind nicht der TBT-Haupttreiber; JSON-Payloads sind moderat, MVT ist für diesen Messstand keine vorrangige Migration.

## Accessibility und Best Practices

Behobene Lighthouse-Findings:

- `html-has-lang`: global `lang="de"` gesetzt.
- `color-contrast`: Footer-Überschriften und Copyright-Zeile von `slate-500` auf `slate-400` angehoben.
- `link-in-text-block`: MapLibre-/OpenStreetMap-Attribution sichtbar unterstrichen.
- Kartenregion mit `aria-label="Interaktive Stadtkarte von Flensburg"` benannt.

Accessibility stieg auf 100. Die mobile Hauptnavigation und Bottom Sheets wurden zusätzlich per Playwright geöffnet/geschlossen; Map- und Detailseiten erzeugten keine JavaScript-Fehler.

Best Practices bleibt bei 96. Der einzige verbleibende automatische Befund ist die erwartete anonyme `401` von `/auth/session`, die Chromium als fehlgeschlagene Netzwerkressource protokolliert. Der unnötige anschließende Refresh wurde entfernt; die Semantik des geschützten Session-Endpunkts wurde nicht aufgeweicht.

## Assets, Caching und Server

- Nitro erzeugt Brotli- und Gzip-Varianten öffentlicher Assets.
- Gehashte `/_nuxt/**`-Assets erhalten `Cache-Control: public, max-age=31536000, immutable`.
- Branding und Kartenstile erhalten einen Browsercache von einem Tag.
- Das SVG-Logo wurde verlustfrei von 106,5 auf 74,4 KB reduziert.
- Das 133,5-KB-ICO wird nicht mehr zusätzlich angefordert; das bestehende SVG dient als Favicon und Logo und wird nur einmal übertragen.
- Bilder behalten explizite Breite/Höhe; keine externen Google-Webfonts oder Tracking-Skripte wurden gefunden.

## Verifikation

- `pnpm test`: 230 Tests bestanden.
- `pnpm typecheck`: bestanden.
- `pnpm build`: bestanden.
- `pnpm test:e2e`: 3 Gebiet-/Statistiktests bestanden.
- zusätzliche Playwright-Smoke-Tests: mobile GIS-Karte geladen, Filter-Bottom-Sheet geöffnet/geschlossen, `/gebiete/flensburg-27020` SSR-Überschrift geprüft, `/flaechen/gisela` samt Karte geladen; keine `pageerror`-Ereignisse.

Die Live-Nachmessung kann erst nach Deployment dieser Änderungen erfolgen. Insbesondere muss der neue Build mit dem abgesicherten `stadtplaner-light`-Default ausgerollt werden; anschließend denselben Lighthouse-Befehl erneut gegen die Produktionsdomain ausführen und CrUX-Felddaten getrennt von diesen Lab-Werten betrachten.
