# Datenbank und Migrationen für Backend-Module

Diese Anleitung beschreibt den Persistence-Contract aus
[ADR #97](../architecture/adr-module-database-and-migration-ownership.md). Alle
Module verwenden dieselbe PostgreSQL-/PostGIS-Datenbank. Ein Modul besitzt ein
Schema und Metadata, keine eigene Datenbank.

## Metadata deklarieren

Das Manifest ist die einzige deklarative Quelle für das Schema:

```json
{
  "persistence": {
    "schema": "example_module",
    "migrations": true
  }
}
```

Tabellen werden explizit qualifiziert:

```python
from sqlalchemy import Column, Integer, MetaData, String, Table

metadata = MetaData()
items = Table(
    "items",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String(120), nullable=False),
    schema="example_module",
)
```

Die passive Definition verbindet Manifest und Metadata:

```python
from app.platform.modules.sdk import (
    ModuleDefinition,
    ModuleMigrationSource,
    ModulePersistenceContribution,
)

DEFINITION = ModuleDefinition(
    manifest=MANIFEST,
    loader=ExampleModule,
    origin="example_module",
    declared_id=MANIFEST.id,
    persistence=ModulePersistenceContribution(
        module_id=MANIFEST.id,
        metadata=metadata,
        schema="example_module",
        migration_source=ModuleMigrationSource(
            package="example_module",
            resource="migrations",
            revision_namespace="mod_example_module",
        ),
    ),
)
```

Der Ressourcenpfad ist relativ zu einem installierten Python-Paket. URLs, absolute
Pfade und Runtime-Downloads sind nicht erlaubt. `register()` wird für Migration
Discovery nicht ausgeführt.

## Migration anlegen

Die erste Revision eines Moduls erstellt das Schema und qualifiziert jede Operation:

```python
revision = "mod_example_module_20260825_0001"
down_revision = "<letzte-geordnete-revision>"


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS example_module")
    op.create_table(
        "items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema="example_module",
    )
```

Revision-IDs beginnen immer mit `mod_<normalisierte-modul-id>_`. Der aktuelle
Contract verwendet einen global linearen Head und keine Branch Labels. Vor dem
Commit müssen Head, Upgrade, expliziter gezielter Downgrade und erneutes Upgrade auf
einer frischen PostGIS-Datenbank geprüft werden.

Eine Migration ändert ausschließlich Tabellen und Schemas ihres Moduls. Für eine
unvermeidbare Cross-Module-Änderung ist vorab ein eigenes Architektur- und
Migrations-Issue erforderlich. Fremde ORM-Modelle werden nicht importiert.

## Reihenfolge und Preflight

Bei der erstmaligen Aufnahme migriert der Host zuerst seine Infrastruktur. Danach
folgen Module in der bereits validierten Dependency-Reihenfolge aus dem Manifest;
unabhängige Module sind nach ID sortiert. Spätere Revisionen werden unabhängig vom
Owner am einen globalen Head angehängt. `MigrationCoordinator.preflight()` prüft:

- genau einen globalen Alembic-Head;
- auflösbare installierte Migrationsressourcen;
- eindeutige Schema-Ownership;
- passende Revision-Namespaces;
- Host- und Modulgruppen in Dependency-Reihenfolge.

Der generische CLI-Einstieg verwendet exakt diese Registry und den aktiven
Modulbestand:

```bash
ENABLED_MODULES=reference uv run python -m app.cli.module_migrations preflight
ENABLED_MODULES=reference uv run python -m app.cli.module_migrations upgrade
```

Vor Erzeugung des Coordinators validiert der CLI-Einstieg die Settings Contributions
aller aktiven Module über dieselbe `ModuleSettingsRegistry` wie die Runtime. Eine
fehlende oder ungültige Modulkonfiguration stoppt damit vor Preflight und Upgrade.
Die vollständige Reihenfolge und Recovery-Policy steht unter
[Modul-Lifecycle](lifecycle.md).

Ein Downgrade akzeptiert absichtlich nur ein explizites Ziel, zum Beispiel
`python -m app.cli.module_migrations downgrade <revision>`.

Migrationen sind vertrauenswürdiger Code mit weitreichenden DB-Rechten. Jede
Revision benötigt manuelles Review; der Preflight ist keine Sandbox.
Reviewed-Community-Migrationen müssen vor Installation vollständig geprüft sein,
dürfen keine stillen Runtime-DDL-Operationen ausführen und ausschließlich die eigene
Persistence-Ownership verändern. Eine Ausnahme benötigt ein explizites Host-
Migrationsreview.

## Session und Transaktionen

`context.database.session()` öffnet eine Host-Session mit einer Transaktionsgrenze.
Der Context Manager committed bei Erfolg und rollt bei Fehler zurück:

```python
if context.database is None:
    raise RuntimeError("database capability required")

async with context.database.session() as session:
    session.add(record)
```

Module importieren weder globale Engine noch `AsyncSessionLocal`. Fachliche
Repositories und ORM-Modelle bleiben im eigenen Modul.
Diese Ownership ist eine Architecture-Grenze, keine PostgreSQL-Sandbox: alle
In-Process-Module teilen faktisch den Hostprozess und Connection Pool.

## Lifecycle und Datenhaltbarkeit

- **Installieren:** Manifest validieren, Preflight, Backup, Migration, danach erst
  aktivieren.
- **Deaktivieren:** Runtime-Beiträge entfernen; kein Downgrade, keine Datenlöschung.
- **Entfernen:** Tabellen bleiben standardmäßig erhalten. Löschen erfolgt nur nach
  expliziter administrativer Entscheidung.
- **Downgrade:** nur mit benannter Zielrevision und geprüftem Datenverlust-/Backup-
  Plan; nie automatisch durch Versions- oder Enablement-Änderungen.

Bereits angewandte Migrationsquellen müssen im Deployment-Inventar auflösbar
bleiben, auch wenn ein Modul deaktiviert ist. Sonst kann Alembic den aktuellen
Datenbankstand nicht sicher koordinieren.

## Legacy und bestehende Daten

`LegacyPersistenceProvider` hält das bestehende `Base.metadata` vollständig im
Autogenerate-Ziel. Bestehende Tabellen verbleiben im bisherigen Schema. Ein späterer
Umzug verwendet eine eigene, geprüfte Migration wie `ALTER TABLE ... SET SCHEMA`;
er ist keine Voraussetzung für neue Module und nicht Teil von #97.

Ein Produktionsmodul, das eine bereits vorhandene Tabelle zunächst ohne physischen
Umzug übernimmt, deklariert diese Tabelle zusätzlich explizit als
`adopted_tables=frozenset({"existing_table"})` in seinem
`ModulePersistenceContribution`. Die Tabelle bleibt unqualifiziert im bisherigen
Schema, muss den unqualifizierten Metadata-Beitrag des Moduls exakt abdecken und wird
dadurch genau einem Modul zugeordnet. Für Alembic Autogenerate bleibt während dieser
Übergangsphase die identische Definition aus `LegacyPersistenceProvider` maßgeblich;
der Modulbeitrag wird dort nicht ein zweites Mal eingespeist. Diese Deklaration
erzeugt weder eine Migration noch eine Tabelle und erlaubt keine pauschale Ownership
des öffentlichen Schemas. Ein Adoption-Beitrag enthält deshalb nicht gleichzeitig
neue schemaqualifizierte Tabellen; diese folgen erst mit einer expliziten
Ownership-Migration, welche die Übergangsdeklaration ersetzt.

Autogenerate schlägt keine Drops für reflektierte Tabellen, Indizes oder Constraints
vor, denen kein registriertes Metadata-Objekt gegenübersteht. Ein echter Drop wird
immer explizit geschrieben und hinsichtlich Ownership und Datenverlust geprüft.

PostGIS bleibt Host-owned. Module dürfen räumliche Typen, Indizes und
schemaübergreifende Funktionen verwenden, installieren oder entfernen die Extension
aber nicht.
