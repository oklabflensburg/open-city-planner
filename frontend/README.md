# Stadtplaner Frontend

Das Nuxt-4-Frontend verbindet die MapLibre-GIS-Anwendung mit öffentlichen Polygon- und Gebietsdetailseiten, Analytics, Dokumentation und SEO-Ausgabe.

## Entwicklung und Build

Die gemessenen Bundle-Grenzen, Produktionsnetzwerk-Werte und Schritte zur
Reproduktion stehen in
[`docs/frontend-build-performance.md`](../docs/frontend-build-performance.md).

```bash
cp .env.example .env
pnpm install --frozen-lockfile
pnpm dev
pnpm test
pnpm typecheck
pnpm build
pnpm audit:language
pnpm audit:seo
```

`NUXT_PUBLIC_API_BASE_URL` zeigt auf die öffentliche FastAPI-Basis (typisch `http://localhost:8000/api/v1`). Optional kann `NUXT_API_INTERNAL_BASE_URL` ausschließlich für serverseitige/SSR-Aufrufe auf eine interne Basis zeigen; ohne den Wert wird die öffentliche API-Basis verwendet. `NUXT_PUBLIC_SITE_URL` muss in Produktion die öffentliche Origin enthalten. Kartenstil, Startposition und optionale Medien-/OG-URLs werden über die Variablen in `.env.example` konfiguriert; ohne externen Kartenstil wird der lokale `stadtplaner-light`-Stil genutzt.

Alle `NUXT_PUBLIC_*`-Werte sind im Browser sichtbar und dürfen keine Secrets enthalten. `NUXT_API_INTERNAL_BASE_URL` bleibt in der privaten Nuxt-Runtime-Konfiguration und darf nicht für Canonical-, OpenGraph-, Twitter-, JSON-LD- oder andere öffentliche URLs verwendet werden. Der produktive Build- und Deploymentablauf steht in [docs/deployment.md](../docs/deployment.md).

## Gebiete, SEO und Sitemap

`/gebiete` rendert die reale Gemeinde-/Stadtteil-/Quartierhierarchie. `/gebiete/[slug]` lädt Detail, Analytics, Vergleich und Flächen serverseitig, setzt Canonical-, Open-Graph-, Twitter- und JSON-LD-Daten und verlinkt bidirektional zur GIS-Auswahl `/?area=<slug>`. Interaktive Kartendaten werden erst clientseitig geladen.

Die XML-Sitemap kombiniert statische Seiten mit dynamischen Polygon- und Analysis-Area-Einträgen aus dem Backend. Nur Gebiete mit valider Geometrie werden geliefert; `updated_at` wird als `lastmod` verwendet.

## Dokumentation

Die öffentliche Dokumentation wird in `app/config/documentation.ts` gepflegt. Navigation, Suche, SEO und Sitemap-Pfade entstehen daraus automatisch. Neue sichtbare Kernfunktionen benötigen einen verständlichen Help-Eintrag, Suchbegriffe und passende Dokumentationstests. Die technische Dokumentationsübersicht liegt unter [docs/README.md](../docs/README.md).

## Superuser-Auditlog

Die nicht indexierbare Route `/admin/audit-log` zeigt das administrative Auditlog ausschließlich Superusern. Sie nutzt den zentralen API-Client, hält Suche, Aktions-, Akteur-, Datums- und Seitenfilter in der URL und zeigt auf kleinen Viewports Cards statt der Desktop-Tabelle. Ereignisdetails öffnen im gemeinsamen Modal und bleiben vollständig read-only; normale Benutzer und reine `VERWALTUNG`-Konten sehen weder den Kontomenüeintrag noch die Seite.

## Kommunale Statistik

Gebietsdetailseiten laden Zahlenspiegel-Kernwerte und die Bevölkerungszeitreihe während SSR aus der lokalen Stadtplaner-API. Gemeinde und Stadtteile zeigen ihre eigene Ebene; Quartiere kennzeichnen ausschließlich die geerbten Werte ihres Parent-Stadtteils. Quelle, Datenstand, Importzeit, Lizenz und der Hinweis zur nicht belegten geometrischen Identität von OSM- und Statistikgrenzen bleiben sichtbar. Die GIS-Sidebar zeigt nur Bevölkerung und Haushalte kompakt an.
