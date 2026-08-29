# ADR: Datenbank- und Migrations-Ownership von Modulen

- Status: Angenommen
- Datum: 2026-08-25
- Entscheidung: [Issue #97](https://github.com/oklabflensburg/open-city-planner/issues/97)
- Epic: [Issue #91](https://github.com/oklabflensburg/open-city-planner/issues/91)
- Grundlage: [ADR #92](adr-modular-host-and-module-boundaries.md)

## Kontext

Open City Planner verwendet produktiv eine gemeinsame PostgreSQL-/PostGIS-Datenbank,
ein zentrales SQLAlchemy-`Base.metadata` und eine veröffentlichte lineare
Alembic-Historie. Bis Revision `20260825_0034` lädt `alembic/env.py` die ORM-Modelle
über eine zentrale Fachmodellliste. Das funktioniert, macht künftige Modulgrenzen
aber unsichtbar und zwingt jede neue Tabelle zu einer Änderung am Host.

Die bestehende Historie und Produktionsdaten dürfen nicht neu aufgebaut werden.
Insbesondere bleibt `20260825_0034` unverändert und als Host-Infrastrukturrevision
für `domain_event_outbox` und `event_delivery` eingeordnet.

## Entscheidung

Der Host und alle Module verwenden weiterhin **eine gemeinsame PostgreSQL-Datenbank
mit genau einer hostverwalteten PostGIS-Extension**. Neue größere Module besitzen
ein explizites PostgreSQL-Schema, ihre eigene SQLAlchemy-`MetaData` und ihre
Migrationen. Der Host besitzt Engine, Session Factory, Transaktionsgrenzen,
DB-Health, PostGIS-Installation, Alembic-Konfiguration und Migrationskoordination.

Die Umstellung erfolgt als Strangler:

```text
Host
├── Engine / Session Factory / Transaktionen
├── PostGIS Extension
├── PersistenceRegistry
├── LegacyPersistenceProvider -> Base.metadata / public
└── Module
    ├── Manifest persistence.schema
    ├── passive ModulePersistenceContribution
    ├── eigenes MetaData
    └── installierte ModuleMigrationSource
```

Bestehende Tabellen bleiben vorerst im bisherigen, überwiegend öffentlichen Schema.
Es gibt in #97 keine fachliche Tabellenverschiebung und keine Datenkopie.

## Schema-Strategie

- Ein neues größeres Fachmodul erhält grundsätzlich ein PostgreSQL-Schema. Der Name
  steht einmalig in `manifest.persistence.schema` und folgt dem vorhandenen
  PostgreSQL-Identifier-Contract.
- Ein Schema hat genau einen Modul-Owner. Doppelte Ownership wird bereits bei der
  Manifestvalidierung und erneut in der Persistence Registry abgelehnt.
- ORM-Tabellen setzen `schema=` explizit. Migrationen verwenden ebenfalls immer
  `schema=` oder schemaqualifiziertes SQL. Der zufällige `search_path` ist kein
  Architekturvertrag.
- Eine Modulmigration legt ihr Schema vor ihrer ersten Tabelle mit
  `CREATE SCHEMA IF NOT EXISTS` an. Rollen- und Benutzerprovisionierung bleibt
  Deployment-Aufgabe und ist nicht Teil dieses Issues.
- Kleine eng zusammengehörige Teilfunktionen dürfen nach Architekturreview ein
  gemeinsames Modulschema verwenden; sie sind dann ein gemeinsamer Persistence-
  Owner und keine zwei unabhängig registrierten Module.

Die ersten möglichen Fachschemas sind beispielsweise `polygons`,
`analysis_areas`, `statistics` und `osm`. Diese Namen sind keine Anweisung, die
heutigen Tabellen jetzt zu verschieben.

## Metadata-Ownership und Discovery

Ein Modul veröffentlicht seine Persistence passiv an seiner bestehenden
`ModuleDefinition`:

```python
ModulePersistenceContribution(
    module_id="example-module",
    metadata=metadata,
    schema="example_module",
    migration_source=ModuleMigrationSource(...),
)
```

Der Schemawert muss mit `manifest.persistence.schema` übereinstimmen. Alle Tabellen
im beigetragenen Metadata-Set müssen explizit im eigenen Schema liegen. Ein Beitrag
darf weder Legacy- noch fremde Modultabellen enthalten.

Die passive Definition ist wichtig: Alembic validiert Metadata und Migrationen,
ohne `BackendModule.register()`, Lifecycle-Hooks, Router, Subscriber oder andere
Runtime-Side-Effects auszuführen. Discovery betrachtet ausschließlich explizit
konfigurierte First-Party-Definitionen und installierte Python Entry Points. Es gibt
keinen Wildcard-Scan mit `pkgutil.walk_packages`.

`LegacyPersistenceProvider` importiert kontrolliert `app.models` und liefert das
bisherige `Base.metadata`. `alembic/env.py` enthält dadurch keine einzelne
Fachmodellliste mehr. Autogenerate erhält eine Sequenz aus Legacy-Metadata und den
geordneten Modul-Metadata-Sets. Die Schemafilter reflektieren nur `public` und
explizit registrierte Modulschemas; PostGIS-Systemschemas werden nicht als
Anwendungsobjekte behandelt. Reflektierte Tabellen, Indizes oder Constraints ohne
registriertes Gegenstück werden konservativ nicht als automatischer Drop erzeugt.
Destruktive Änderungen benötigen dadurch immer eine explizite reviewte Migration.

## Migrationsquellen und Sicherheit

`ModuleMigrationSource` verweist ausschließlich auf einen relativen Ressourcenpfad
in einem bereits installierten Python-Paket. URLs, absolute Pfade und
Verzeichnis-Traversal sind ungültig. Es gibt keine Runtime-Downloads und keine
Shell-Ausführung durch den Contract.

Installierte Module sind weiterhin vertrauenswürdiger In-Process-Code, keine
Sandbox. Migrationen besitzen besonders weitreichende Datenbankrechte und benötigen
deshalb zwingend Review. Automatische Ownership-Prüfungen ergänzen dieses Review,
ersetzen es aber nicht; dynamisches SQL kann nicht vollständig statisch bewiesen
werden.

## Alembic-Heads und Revision-Naming

V1 behält **einen globalen linearen Alembic-Head** bei. Mehrere Branch-Heads pro
Modul wurden verworfen, weil sie Deployment, Downgrade, Autogenerate und externe
Modulupdates deutlich komplexer machen und der aktuelle Monolith keinen Nutzen aus
parallelen Heads zieht. Alembic bleibt alleinige Source of Truth; eine zusätzliche
`module_migration_state`-Tabelle wird nicht eingeführt.

Modulrevisionen verwenden die kollisionsarme Konvention:

```text
mod_<normalisierte-modul-id>_<YYYYMMDD>_<sequence>
```

Für `analysis-areas` ist der Namespace beispielsweise `mod_analysis_areas`.
Branch Labels werden in V1 nicht verwendet. Eine neu erstellte Host- oder
Modulmigration referenziert mit `down_revision` stets den aktuellen globalen Head.
Historische, später von einem Modul adoptierte Revisionen dürfen dagegen mit Host-
Revisionen verschachtelt sein und bilden keine zusammenhängende Modulgruppe. Source-
Ownership und Ownership der direkten Parent-Revision sind unabhängig: Hostrevisionen
dürfen auf Modulrevisionen und Modulrevisionen auf Hostrevisionen folgen. Damit bleibt
der Graph linear.

Eine spätere Domain-Externalisierung darf veröffentlichte Host-Revisionen explizit
über `ModuleMigrationSource.adopted_revisions` übernehmen. Diese Adoption ändert
nur den Source-Code-Owner; Revisions-ID, Elternbeziehung und bereits ausgeführter
DB-Zustand bleiben unverändert. Nicht adoptierte neue Modulrevisionen müssen
weiterhin den Modulnamespace verwenden. Doppelte Revisionen zwischen Host und
Modul oder zwischen Modulen sind immer ein Preflight-Fehler und werden nicht durch
die Reihenfolge der `version_locations` aufgelöst.

## Deterministische Reihenfolge

Für die erstmalige Aufnahme von Modulen lautet die Reihenfolge:

1. Host-/Legacy-Revisionen;
2. Module in der bereits durch #93 aufgelösten Dependency-Reihenfolge;
3. innerhalb eines Moduls dessen eigene Revisionsreihenfolge.

Unabhängige Module werden wie im bestehenden Resolver lexikografisch nach Modul-ID
geordnet. Spätere Host- oder Modulrevisionen werden am globalen Head angehängt und
dürfen deshalb über Releases hinweg zwischen Ownern wechseln; ihre `down_revision`
bleibt die eindeutige Reihenfolge. Der `MigrationCoordinator` verwendet denselben
aufgelösten Katalog und implementiert keine zweite Graphlogik. Sein Preflight prüft
genau einen Head, auflösbare installierte Quellen, Revision-Namespaces und die
Dependency-Reihenfolge der initialen Modulrevisionen.

Der aktuelle Production-Pfad `alembic upgrade head` bleibt für die bestehende
Host-/Legacy-Historie unverändert. Sobald ein deploytes Modul echte Migrationen
liefert, muss der Deployment-Schritt dessen installierte Quellen in den Coordinator
geben und den Preflight vor dem Upgrade ausführen. Die Migrationsinventur umfasst
dabei auch installierte, aber deaktivierte Module, deren Revisionen bereits in der
Datenbank stehen; Deaktivierung entfernt weder Paket noch Historie.

## Cross-Module-Beziehungen

Cross-Module-Foreign-Keys sind seltene, explizite Ausnahmen. Bevorzugt werden IDs und
versionierte Query-/Service-Contracts statt Imports fremder ORM-Modelle. Ist ein FK
fachlich unvermeidbar, müssen dokumentiert sein:

- Owner der Quell- und Zieltabelle;
- passende Manifestabhängigkeit;
- Erstellungs- und Migrationsreihenfolge;
- `ON DELETE`-/`ON UPDATE`-Semantik;
- Verhalten bei Deaktivierung und inkompatiblen Modulversionen.

Eine Migration darf nie eigenmächtig eine fremde Tabelle ändern. Solche Änderungen
benötigen ein eigenes Architektur-/Migrations-Issue und Review beider Owner.
Schemaübergreifende räumliche Abfragen bleiben erlaubt. Module exponieren sie nach
außen über Query-/Service-Contracts statt über fremde ORM-Imports.

## PostGIS

Die Extension `postgis` wird genau einmal vom Host beziehungsweise der
Betriebsumgebung bereitgestellt. Module dürfen Geometry-/Geography-Spalten,
räumliche Indizes und Funktionen wie `ST_Intersects` oder `ST_DWithin` verwenden.
Sie dürfen die Extension weder installieren noch entfernen. Explizit qualifizierte
Modultabellen verhindern schemaabhängige Unterschiede zwischen Umgebungen.

## Installieren, Deaktivieren und Entfernen

Installation folgt fail-closed:

1. Manifest und Kompatibilität validieren;
2. Persistence-Ownership und Migrationsquellen im Preflight prüfen;
3. Backup und Zielrevisionen prüfen;
4. Migrationen in Host-/Dependency-Reihenfolge ausführen;
5. erst nach erfolgreicher Migration das Modul aktivieren.

Schlägt eine Migration fehl, stoppt das Deployment. Der Fehler enthält nach
Möglichkeit Modul-ID, Revision, Schema und Phase. Erfolgreich abgeschlossene frühere
Revisionen bleiben über Alembic diagnostizierbar; die fehlgeschlagene Revision wird
bei transaktionaler DDL zurückgerollt.

Deaktivieren entfernt Router, Jobs und Subscriber, führt aber **keinen Downgrade**
aus. Tabellen, Alembic-Quellen und Daten bleiben erhalten. Auch das Entfernen eines
Modulpakets darf Tabellen nicht automatisch löschen. Zuerst muss eine explizite,
administrativ bestätigte Datenhaltungs-/Export-/Löschentscheidung erfolgen.

Downgrades werden nur mit einer expliziten Zielrevision ausgeführt. Ein
Modulversionswechsel oder eine geänderte Enablement-Liste löst niemals still einen
Downgrade aus. Vor einem Downgrade werden aktuelle Version, Zielversion,
Kompatibilität, Datenverlust und Backup geprüft.

## Production-Migrationsstrategie

- Veröffentlichte Revisionen bis einschließlich `20260825_0034` bleiben in ihrer
  Identität und Historie unverändert. Ihr Source-Code kann bei einer späteren
  Domain-Externalisierung explizit und exklusiv von einem Modul adoptiert werden.
- Bestehende Tabellen verbleiben zunächst im aktuellen Schema und im
  `LegacyPersistenceProvider`.
- Eine spätere Fachmigration darf Tabellen schrittweise mit
  `ALTER TABLE ... SET SCHEMA` oder einer geprüften Copy-/Rename-Strategie
  übernehmen. Sie benötigt ein eigenes Issue, Backup-, Locking-, Laufzeit- und
  Rollback-Konzept.
- Es gibt keinen Datenbank-Rebuild und keinen Reimport von Production-Daten.
- Ein fehlgeschlagenes Migrationspreflight beziehungsweise Upgrade verhindert die
  Aktivierung des neuen Releases.
- Nach einem Domain-Cutover liegt deren vollständige historische Migration History
  ausschließlich im Modulpaket; adoptierte Dateien dürfen dann nicht parallel im
  Host-Alembic-Verzeichnis verbleiben.

## Observability

Migrationslogs verwenden die niedrig-kardinalen Felder `module_id`, `revision`,
`schema` und `migration_phase`. Gültige Phasen sind `preflight`,
`adoption_validation`, `upgrade_started`, `upgrade_completed` und
`upgrade_failed`. Verbindungs-URLs, SQL-Payloads und Secrets werden nicht
protokolliert.

## Folgen

Neue Module können Tabellen besitzen, ohne die zentrale Alembic-Modellimportliste zu
erweitern. Schemas machen Ownership und Namenskollisionen sichtbar, während
Cross-Schema-PostGIS-Abfragen erhalten bleiben. Die bestehende Datenbank, Historie
und der Production-Deploy bleiben kompatibel.

Der Preis ist eine koordinierte lineare Revisionserstellung: unabhängige Module
können nicht beliebig gleichzeitig neue Heads veröffentlichen. Für den modularen
Monolithen ist diese geringere Komplexität derzeit wichtiger. Sollte echte externe
Distribution später parallele Release-Zyklen erfordern, muss ein neues ADR mehrere
Heads oder eine andere Koordination bewerten; #97 führt sie nicht vorsorglich ein.
