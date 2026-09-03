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

Alle `NUXT_PUBLIC_*`-Werte sind im Browser sichtbar und dürfen keine Secrets enthalten. Ohne `NUXT_PUBLIC_DEFAULT_OG_IMAGE` verwendet die Anwendung die statische 1200×630-Stadtplaner-Karte unter `/branding/stadtplaner-social-card.png`; konfigurierte Alternativen müssen ebenfalls 1200×630 Pixel groß sein. `NUXT_API_INTERNAL_BASE_URL` bleibt in der privaten Nuxt-Runtime-Konfiguration und darf nicht für Canonical-, OpenGraph-, Twitter-, JSON-LD- oder andere öffentliche URLs verwendet werden. Der produktive Build- und Deploymentablauf steht in [docs/deployment.md](../docs/deployment.md).

Die aus dem vorhandenen OK-Lab-Branding abgeleiteten PNG-Icons und die Standard-Social-Karte lassen sich mit `pnpm assets:seo` reproduzierbar neu erzeugen.

## Optionale Gebiete, SEO und Sitemap

Die Routen `/gebiete` und `/gebiete/[slug]` gehören nicht zum Host. Ein aktiviertes
Analysis-Areas-Modul kann sie als Nuxt-Layer beitragen, Daten serverseitig laden,
Canonical-, Open-Graph-, Twitter- und JSON-LD-Daten setzen und zur GIS-Auswahl
verlinken. Ohne aktiviertes Modul existieren weder die Routen noch ihre
Kartenbeiträge.

Die XML-Sitemap kombiniert statische Seiten und dynamische Polygoneinträge mit den
Beiträgen aktivierter Module. Nur deklarierte Sitemap-Contributions lösen ihre
jeweiligen Backend-Abfragen aus; ohne Analysis-Areas-Modul gibt es weder
Gebietseinträge noch einen Gebiets-Sitemap-Fetch.

## Dokumentation

Die öffentliche Dokumentation wird in `app/config/documentation.ts` gepflegt. Navigation, Suche, SEO und Sitemap-Pfade entstehen daraus automatisch. Neue sichtbare Kernfunktionen benötigen einen verständlichen Help-Eintrag, Suchbegriffe und passende Dokumentationstests. Die technische Dokumentationsübersicht liegt unter [docs/README.md](../docs/README.md).

## Superuser-Auditlog

Die nicht indexierbare Route `/admin/audit-log` zeigt das administrative Auditlog ausschließlich Superusern. Sie nutzt den zentralen API-Client, hält Suche, Aktions-, Akteur-, Datums- und Seitenfilter in der URL und zeigt auf kleinen Viewports Cards statt der Desktop-Tabelle. Ereignisdetails öffnen im gemeinsamen Modal und bleiben vollständig read-only; normale Benutzer und reine `VERWALTUNG`-Konten sehen weder den Kontomenüeintrag noch die Seite.

Kommunale Statistik ist ebenfalls kein Hostbestandteil. Fachmodule können sie über
die dokumentierten öffentlichen Service- und UI-Verträge zusammensetzen.
