# Stadtplaner Frontend

Das Nuxt-4-Frontend verbindet die MapLibre-GIS-Anwendung mit öffentlichen Polygon- und Gebietsdetailseiten, Analytics, Dokumentation und SEO-Ausgabe.

## Entwicklung und Build

```bash
cp .env.example .env
pnpm install
pnpm dev
pnpm test
pnpm typecheck
pnpm build
```

`NUXT_PUBLIC_API_BASE_URL` zeigt auf die FastAPI-Basis (typisch `http://localhost:8000/api/v1`). `NUXT_PUBLIC_SITE_URL` muss in Produktion die öffentliche Origin enthalten. Kartenstil, Startposition und optionale Medien-/OG-URLs werden über die Variablen in `.env.example` konfiguriert; ohne externen Kartenstil wird der lokale `stadtplaner-light`-Stil genutzt.

## Gebiete, SEO und Sitemap

`/gebiete` rendert die reale Gemeinde-/Stadtteil-/Quartierhierarchie. `/gebiete/[slug]` lädt Detail, Analytics, Vergleich und Flächen serverseitig, setzt Canonical-, Open-Graph-, Twitter- und JSON-LD-Daten und verlinkt bidirektional zur GIS-Auswahl `/?area=<slug>`. Interaktive Kartendaten werden erst clientseitig geladen.

Die XML-Sitemap kombiniert statische Seiten mit dynamischen Polygon- und Analysis-Area-Einträgen aus dem Backend. Nur Gebiete mit valider Geometrie werden geliefert; `updated_at` wird als `lastmod` verwendet.

## Dokumentation

Die öffentliche Dokumentation wird in `app/config/documentation.ts` gepflegt. Navigation, Suche, SEO und Sitemap-Pfade entstehen daraus automatisch. Die Gebiets-, Methodik- und API-Seiten erläutern die öffentliche Hierarchie, reale Aggregationslogik und Links zur OpenAPI-Dokumentation.

## Superuser-Auditlog

Die nicht indexierbare Route `/admin/audit-log` zeigt das administrative Auditlog ausschließlich Superusern. Sie nutzt den zentralen API-Client, hält Suche, Aktions-, Akteur-, Datums- und Seitenfilter in der URL und zeigt auf kleinen Viewports Cards statt der Desktop-Tabelle. Ereignisdetails öffnen im gemeinsamen Modal und bleiben vollständig read-only; normale Benutzer und reine `VERWALTUNG`-Konten sehen weder den Kontomenüeintrag noch die Seite.

## Kommunale Statistik

Gebietsdetailseiten laden Zahlenspiegel-Kernwerte und die Bevölkerungszeitreihe während SSR aus der lokalen Stadtplaner-API. Gemeinde und Stadtteile zeigen ihre eigene Ebene; Quartiere kennzeichnen ausschließlich die geerbten Werte ihres Parent-Stadtteils. Quelle, Datenstand, Importzeit, Lizenz und der Hinweis zur nicht belegten geometrischen Identität von OSM- und Statistikgrenzen bleiben sichtbar. Die GIS-Sidebar zeigt nur Bevölkerung und Haushalte kompakt an.
