# Frontend-Build und Bundle-Grenzen

Stand: 17. August 2026. Gemessen wurde lokal mit Nuxt 4.5.2, Vite 8.2.1,
Rolldown 1.2.3 und Node.js 22.22.3. Die Werte sind Diagnosewerte derselben
Maschine und keine Web-Vitals-Messung.

## Ergebnis

Die großen Bibliotheken sind bereits fachlich getrennt:

- MapLibre wird dynamisch aus den Kartenkomponenten importiert. Sein erzeugter
  Chunk ist mit 1.027.753 Byte zwar groß, enthält laut Nuxt-Visualizer aber nur
  das monolithische `maplibre-gl`-Distributionsmodul. Eine weitere künstliche
  Aufteilung auf App-Ebene würde keine belastbare Ladegrenze schaffen.
- Chart.js wird modular mit `ArcElement`, `BarElement`, `CategoryScale`,
  `LinearScale`, `Tooltip` und `Legend` registriert. Der Chart-Chunk ist 171.597
  Byte groß und wird auf Mobilgeräten erst beim Öffnen von „Analyse“ geladen.
- Terra Draw (218.572 Byte) bleibt ein eigener Editor-Chunk.
- Dokumentation, Anmeldung und Admin-Seiten bleiben eigene Routen-Chunks.

Die globale Link-Vorablade-Strategie ist auf Interaktion gestellt. Dadurch lädt
ein sichtbarer Header-Link nicht mehr automatisch seine Route. Der GIS-Filter-
URL-Abgleich wird außerdem nur zusammen mit der Kartenanwendung aktiviert; die
Benachrichtigungsoberfläche wird nur für angemeldete Nutzer asynchron geladen.

## Reproduzierbare Messungen

```bash
cd frontend
pnpm exec nuxt analyze --no-serve
/usr/bin/time -v pnpm build
du -sh .output .output/server .output/public
find .output/public/_nuxt -type f -name '*.js' -printf '%s %f\n' | sort -nr
```

Der Visualizer liegt nach dem Analyse-Build unter
`frontend/node_modules/.cache/nuxt/.nuxt/analyze/client.html`. Er ist ein lokales
Artefakt und wird nicht eingecheckt.

| Messwert | Vorher | Nachher |
| --- | ---: | ---: |
| normaler Warm-Build, Wandzeit | 23,47 s | 26,99 s |
| Client-Bundle | 6,40 s | 7,01 s |
| Server-Bundle | 3,01 s | 3,63 s |
| maximaler RSS | 1.792 MB | 1.843 MB |
| `.output` auf Datenträger | 13 MB | 13 MB |
| Dateien in `.output` | 628 | 631 |
| Nitro-Server-Bundle | 5,27 MB | 5,28 MB |

Die Einzelmessungen zeigen keine Build-Zeit-Verbesserung; die Abweichung liegt
innerhalb der beobachteten Schwankung warmer Builds. Der Nuxt-Report ordnet 13,8
von 27,6 Sekunden dem Nitro-Build zu. Besonders teuer sind dort die
`nitro:node-externals`- und `nitro:alias`-Auflösungen. Ein CPU-Profil mit 25.765
Samples bestätigt Dateisystem-Stat-Aufrufe, Rolldown-JSON-/Source-Map-Verarbeitung,
Rollup-Source-Map-Decoding und Garbage Collection als relevante CPU-Anteile. Es
gibt keinen einzelnen langsamen Anwendungstransform, der durch Chunk-Konfiguration
behoben würde.

## Produktionsnetzwerk

Gemessen mit einem frischen Chromium-Kontext pro Route gegen den lokalen
Production-Server. API-Antworten waren deterministisch gemockt; „Byte“ bezeichnet
die Summe der übertragenen minifizierten JS-Ressourcen vor HTTP-Kompression.

| Route/Zustand | JS-Anfragen | JS-Byte | Chunks ab 150 kB |
| --- | ---: | ---: | --- |
| `/impressum` | 45 | 313.716 | keine |
| `/datenschutz` | 45 | 325.911 | keine |
| `/dokumentation` | 49 | 380.433 | keine |
| `/login` | 50 | 325.636 | keine |
| `/admin/social`, Superuser | 57 | 347.372 | keine |
| `/`, Desktop | 73 | 1.693.790 | MapLibre, Chart.js |
| `/`, Mobil, initial | 70 | 1.516.301 | MapLibre |
| `/`, Mobil, nach „Analyse“ | 73 | 1.693.790 | MapLibre, Chart.js |

Vor der geänderten NuxtLink-Konfiguration holten sichtbare globale Links auf
Inhaltsseiten 82 bis 83 JS-Dateien. Danach sind es 45 auf Impressum/Datenschutz
beziehungsweise 49 in der Dokumentation. Das sind 37 beziehungsweise 34 weniger
Requests. Karten-, Chart- und Admin-Code erscheint nicht in den Inhaltsrouten.

## Bewusste Entscheidungen

- Die 500-kB-Warnung für MapLibre wird nicht hochgesetzt oder versteckt. Sie
  dokumentiert weiterhin die reale Größe des optionalen Kartenfeatures.
- Es gibt keine pauschalen Vendor-Chunks. Dynamische Imports an fachlichen
  Grenzen sind stabiler als dateinamen- oder paketbasierte Zwangsaufteilungen.
- Client-Production-Sourcemaps werden nicht erzeugt. Die kleinen serverseitigen
  Nitro-Sourcemaps bleiben für Fehlerdiagnosen erhalten.
- Build-Caches werden bei normalen Builds nicht gelöscht. Für Vergleichswerte
  werden Warm-Builds mit identischer Konfiguration verwendet.

