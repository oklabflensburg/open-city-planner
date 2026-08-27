# Analysis Areas module

`analysis-areas` ist das erste aus einer bestehenden Produktionsdomäne migrierte
Open-City-Planner-Modul. Es verwendet die physische Tabelle `analysis_areas` und
sämtliche bisherigen öffentlichen URLs unverändert weiter.

## Ownership

Das Modul besitzt Gebietsidentität, UUID, Slug, Typ, Hierarchie, Geometrie,
öffentliche Liste/Details, GeoJSON und Sitemap-Metadaten. Sein Manifest deklariert
die Capabilities `analysis-areas.public-api`, `analysis-areas.lookup` und
`analysis-areas.geojson`. Mutationen oder eigene Jobs existieren derzeit nicht;
deshalb werden dafür keine künstlichen Permissions, Events oder Jobs registriert.

Die Tabelle wird über den additiven `adopted_tables`-Persistence-Contract
registriert. Es gibt keine neue Tabelle, keine Datenkopie, kein Rename und keine
Änderung an SRID, Geometrietyp, Constraints oder historischer Alembic-History.
Deaktivieren entfernt Runtime-Beiträge, niemals persistierte Datensätze.

## Öffentliche Verträge

Der FastAPI-Router wird über `ModuleContext.api` unter dem bestehenden Prefix
`/api/v1/analysis-areas` eingebunden. `analysis-areas.lookup` Version 1 liefert
materialisierte, persistence-freie DTOs für ID-/Slug-Lookup, Geometrie und
Hierarchie. Consumer erhalten weder SQLAlchemy-Modelle noch Sessions.

Statistics, Analytics, Polygons, Map Preview, Cache und Public Query Security
behalten ihre bisherige Ownership. Die Produktion-Endpunkte dafür liegen bis zur
Migration der Consumer hinter `integrations/legacy.py`. Jede private Abhängigkeit
ist in der Architecture Baseline exakt benannt und mit #108, #128 oder #129
verknüpft. Neue Modulpfade dürfen diese Adapter nicht ausweiten.

## Aktivieren und deaktivieren

Backend-Produktion aktiviert die bestehende Kernfunktion standardmäßig:

```env
ENABLED_MODULES=analysis-areas
```

Ein gezielter Disabled-Test setzt `ENABLED_MODULES=`. Dann fehlen Router,
Capabilities und der Lookup-Service; die Tabelle bleibt erhalten. Das Frontend
verwendet entsprechend:

```bash
export ENABLED_MODULES=analysis-areas
export OCP_BACKEND_MODULES="$(scripts/backend-module-inventory --format env)"
cd frontend
export OCP_FRONTEND_MODULES=analysis-areas
```

Die Backend-Version stammt dabei ausschließlich aus `MANIFEST` und wird nicht in
Frontend-, CI- oder Deployment-Konfiguration dupliziert.

## Verifikation

Die fokussierten Modul-, Characterization-, API-, Persistence-, SSR-, SEO-, Map-
und Enabled/Disabled-Tests sind Teil des Module Contract Gate. Die vollständigen
Kommandos und Ergebnisse stehen in der PR-Beschreibung.
