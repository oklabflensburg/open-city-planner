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

## Historische Revisionen adoptieren

Beim Externalisieren einer bestehenden Fachdomäne wechselt die Ownership des
Migrationsquellcodes, nicht die Identität oder Ausführungshistorie der Migration.
Das Modul deklariert jede übernommene Alembic-ID statisch an seiner einzigen
`ModuleMigrationSource`:

```python
ModuleMigrationSource(
    package="ocp_module_example",
    resource="migrations",
    revision_namespace="mod_example",
    adopted_revisions=frozenset({
        "20260101_0001",
        "20260201_0002",
    }),
)
```

Die Dateien, ihre `revision`, `down_revision`, `branch_labels` und `depends_on`
bleiben unverändert. Adoptierte Revisionen dürfen im globalen Graphen mit Host-
Revisionen verschachtelt sein; sie müssen weder einen zusammenhängenden Block bilden
noch am aktuellen Head enden. Eine neue Modulrevision verwendet weiterhin den
Modulnamespace und wird wie jede neue Migration an den zu diesem Zeitpunkt aktuellen
globalen Head angehängt:

```python
revision = "mod_example_0001"
down_revision = "<aktueller-globaler-head>"
```

Direkt an die letzte adoptierte Revision darf sie nur anschließen, wenn diese
zugleich der aktuelle globale Head ist. Andernfalls entstünde neben den späteren
Host-Revisionen ein zweiter Head, und der Preflight stoppt.

Source-Ownership bestimmt dabei nicht die Parent-Ownership: Eine Hostrevision darf
auf eine adoptierte Modulrevision folgen und eine neue Modulrevision auf eine
Hostrevision. Die `MigrationStep`-Planung darf entsprechend mehrfach zwischen Host
und Modul wechseln.

Der Coordinator akzeptiert eine nicht namespacete Modulrevision ausschließlich,
wenn ihre exakte ID in `adopted_revisions` steht. Er stoppt bei deklarierten, aber
fehlenden Revisionen, nicht deklarierten historischen IDs sowie jeder doppelten ID
zwischen Host und Modul oder zwei Modulen. Es gibt kein Deduping nach Lade- oder
Dateisystemreihenfolge und keine Ableitung aus Datei-, Tabellen- oder Modulnamen.

Die Analysis-Areas-Referenzdateien heißen beispielsweise
`20260814_0014_analysis_areas.py`, `20260817_0023_area_wikidata.py`,
`20260818_0025_osm_external_links.py` und
`20260819_0032_optimize_area_poi_analytics.py`; ihre tatsächlichen stabilen
Alembic-IDs sind `20260814_0014`, `20260817_0023`, `20260818_0025` und
`20260819_0032`.

Seit dem finalen Analysis-Areas-Cutover liegen diese Dateien ausschließlich im
externen Modulpaket und nicht mehr im Host-`versions`-Verzeichnis. Eine bereits
auf einer adoptierten Revision stehende Datenbank benötigt weder `stamp`,
Baseline noch Reparatur und führt die Revision nicht erneut aus.

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
- vollständige Adoption-Metadaten und kollisionsfreie Revision-Ownership;
- passende Revision-Namespaces für alle neuen, nicht adoptierten Modulrevisionen;
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

Die Persistence Registry des Coordinators wird bewusst aus einer zweiten,
enablement-unabhängigen Menge aufgebaut. Sie entdeckt passive Definitionen aller
lokalen Built-ins unter `app/modules/*/module.py` und aller installierten Entry
Points aus `open_city_planner.modules`. Für separat installierte Pakete liest der
Migrations-CLI alle Backend-Roots direkt aus dem strict validierten `modules.lock`
und stellt diese Pfade ausschließlich scoped für Discovery und Coordinator bereit.
Danach wird `sys.path` exakt wiederhergestellt. Damit bleiben Migrationsquellen
deaktivierter Module im Alembic-Graph, obwohl diese Module nicht registriert oder
gestartet werden. Der Modul-Loader wird bei dieser Discovery nicht aufgerufen.

Manifeststruktur, Persistence-Ownership und die lesbare Dependency-Reihenfolge
bleiben für den Graph erforderlich. Host-/SDK-Compatibility und Modulsettings eines
deaktivierten Moduls sind dagegen kein Runtime-Gate. Fehlende Secrets eines
deaktivierten Moduls blockieren den Preflight daher nicht. Der
[Installer aus #173](installer.md) hält deaktivierte Backend-Pfade deshalb im
Installationszustand verfügbar, ohne sie dem Runtime-Importpfad hinzuzufügen.

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
