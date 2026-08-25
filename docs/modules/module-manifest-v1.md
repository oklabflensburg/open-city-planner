# Module Manifest Schema V1

Diese Dokumentation präzisiert den maschinenlesbaren Modulvertrag aus
[ADR: Modularer Host und Grenzen von Fachmodulen](../architecture/adr-modular-host-and-module-boundaries.md).
Die darauf aufbauende Discovery und Registrierung beschreibt die
[Backend-Module-Runtime](backend-module-runtime.md). Der vollständige
Aktivierungs-Lifecycle und die Distribution bleiben Gegenstand von #112 und #113.

## Contract und Formate

`ModuleManifestV1` in `backend/app/platform/modules/manifest.py` ist die typisierte
Single Source of Truth. Das daraus erzeugte, versionierte
[JSON Schema](schema/module-manifest-v1.schema.json) ist für externe Werkzeuge
committed. Ein Test verhindert Abweichungen zwischen Pydantic-Modell und Datei.

Der Parser akzeptiert ein bereits dekodiertes Python-Mapping. JSON ist damit direkt
nutzbar. YAML darf ein Authoring-Format sein, ist aber kein eigener Contract und wird
vom Host in V1 nicht geladen. Ein späterer Dateiloader muss für YAML ausschließlich
einen Safe Loader verwenden. Manifestwerte werden nicht als Python-Import,
Shell-Befehl, SQL oder Template ausgeführt; Package-Referenzen sind nur Strings.

Unbekannte Felder sind auf jeder Schemaebene verboten. Dadurch wird zum Beispiel
`permisions` nicht stillschweigend ignoriert. Capability-IDs bleiben dagegen offen:
Ein älterer Host darf eine syntaktisch gültige, ihm noch unbekannte Capability
transportieren.

## Versionen

Der Contract unterscheidet drei Versionen:

1. `manifest_version` versioniert das Schema. V1 akzeptiert ausschließlich den Wert
   `1`; andere Werte schlagen mit `UnsupportedManifestVersionError` fehl.
2. `version` ist die vollständige SemVer-Version des Moduls, zum Beispiel `2.3.1`.
3. `requires.host`, `requires.sdk` und Modulabhängigkeiten sind Compatibility-Ranges.

V1 verwendet genau eine Range-Sprache: komma-separierte, explizite Vergleiche mit
vollständigen SemVer-Versionen, zum Beispiel `>=1.2.0,<2.0.0`. Erlaubte Operatoren
sind `>=`, `<=`, `>`, `<`, `==` und `!=`. Npm-Kurzformen wie `^1.2.0`, `~1.4.0`,
Wildcards und unvollständige Versionen sind nicht Teil des Contracts. Parsing und
Vergleich erfolgen mit `python-semanticversion`; das Manifest verwendet weder
PEP-440- noch npm-Range-Semantik.

Die spätere Runtime übergibt ihre Versionen explizit:

```python
validated = validate_manifests(
    manifests,
    host_version="1.0.0",
    sdk_version="1.0.0",
)
order = resolve_module_order(validated)
```

Der Validator sucht Versionen nicht selbst in Paketen, Settings oder im Netzwerk.
Host, SDK und Module folgen langfristig SemVer; Details zu Compatibility und
Deprecation bleiben Teil von #93/#94.

## Identität und IDs

Modul-IDs sind stabile ASCII-IDs in lowercase kebab-case. Sie erfüllen
`^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$`, sind höchstens 63 Zeichen lang und hängen nicht
vom Anzeigenamen ab:

```json
{
  "id": "analysis-areas",
  "name": "Analysegebiete"
}
```

Eine ID darf nicht ohne eigenes Migrations- und Compatibility-Konzept umbenannt
werden. Zwei verfügbare Manifeste mit derselben ID schlagen fail-fast fehl; bekannte
Manifestquellen können für die Fehlermeldung separat an `validate_manifests`
übergeben werden.

Capability- und Permission-IDs verwenden mindestens zwei durch Punkte getrennte,
ebenfalls kebab-case-formatierte Segmente. Capabilities wie `map.layer`,
`map.feature-info`, `analysis.provider`, `ui.navigation`, `jobs.provider` und
`events.publisher` werden nur validiert, dedupliziert und transportiert. V1 führt
keine abschließende Capability-Registry ein.

Moduldefinierte Permissions müssen mit `<module-id>.` beginnen, zum Beispiel
`example-biotopes.read`. Host/Core-Permissions werden nicht über ein Fachmanifest
definiert. Auswertung und Registrierung der Permissions folgen in #104.

## Felder

| Feld | Bedeutung |
|---|---|
| `manifest_version` | Version des Manifest-Schemas, in V1 exakt `1` |
| `id` | stabile technische Modul-ID |
| `name` | menschenlesbarer Anzeigename |
| `version` | vollständige SemVer-Modulversion |
| `requires.host` | kompatible Host-Versionen |
| `requires.sdk` | kompatible Public-SDK-Versionen |
| `requires.modules` | erforderliche Module und deren Ranges |
| `optional.modules` | optionale Module und deren Ranges |
| `backend.package` | optionaler Python-Distributionsbezeichner |
| `frontend.package` | optionaler npm-Paketbezeichner |
| `capabilities` | offene, stabile Capability-IDs |
| `permissions` | stabile, vom Modul namespacete Permission-IDs |
| `config.namespace` | eindeutige Identität für die spätere Config Runtime aus #99 |
| `persistence.schema` | deklarativer, unquoted-sicherer PostgreSQL-Schemaname |
| `persistence.migrations` | kündigt eigene Migrationen für #97 deklarativ an |

Backend-only-, Frontend-only- und kombinierte Module sind darstellbar. Die
Package-Felder lösen in #93 weder Imports noch Downloads aus. Das Manifest enthält
keine Secrets, SQL-Anweisungen, Entry-Point-Ausführung oder Settingswerte.

`config.namespace` ist über die validierte Manifestmenge eindeutig und stabil.
Environment-Namen, Secret-Zugriff und Settings-Lifecycle werden erst in #99
definiert. Persistence-Metadaten erzeugen weder DB-Schemas noch Migrationen; der
Alembic-Runner bleibt bis #97 unverändert.

## Dependency-Semantik

Eine Required Dependency muss in der vom Aufrufer bereitgestellten Menge vorhanden
und versionskompatibel sein. Fehlt sie, entsteht ein
`MissingModuleDependencyError`; bei falscher Version ein
`ModuleDependencyVersionError`.

Eine Optional Dependency darf fehlen. Ist sie vorhanden, muss ihre Version zur
deklarierten Range passen; eine inkompatible vorhandene Version ist ebenfalls ein
Fehler. Optional bedeutet nur, dass ein Modul zusätzliche Funktionalität nutzen
kann. Es aktiviert oder lädt kein anderes Modul.

Der Validator kennt keinen Enable/Disable-Zustand. #94/#112 übergeben ausschließlich
die für den jeweiligen Bootstrap verfügbaren beziehungsweise aktiven Manifeste.
Required und optional Self Dependencies sind verboten. Modulabhängigkeiten müssen
deklariert sein; Host und SDK sind separate Compatibility Targets und werden nicht
als künstliche Module modelliert.

## Graph und Load Order

`resolve_module_order()` führt einen topologischen Sort auf validierten Manifesten
aus. Dependencies stehen stets vor ihren Consumern. Sind mehrere Module gleichzeitig
ladbar, entscheidet die Modul-ID lexikografisch. Dadurch bleiben Startreihenfolge,
Logs und Tests unabhängig von Discovery- oder Dateisystemreihenfolge reproduzierbar.

Vorhandene optionale Dependencies bilden ebenfalls eine Sortierkante. Duplicate IDs,
Self Dependencies, fehlende Required Dependencies und direkte oder indirekte Zyklen
schlagen hart fehl. Ein Zyklusfehler enthält einen konkreten, deterministischen Pfad,
zum Beispiel:

```text
module-a -> module-b -> module-c -> module-a
```

## Strukturierte Fehler

- `ModuleManifestError`
- `UnsupportedManifestVersionError`
- `InvalidRuntimeVersionError`
- `DuplicateModuleIdError`
- `DuplicateConfigNamespaceError`
- `ModuleCompatibilityError`
- `MissingModuleDependencyError`
- `ModuleDependencyVersionError`
- `ModuleSelfDependencyError`
- `ModuleDependencyCycleError`

Die Fehler tragen je nach Fall Modul-ID, erwartete und gefundene Version,
Dependency-ID, bekannte Origins oder den Cycle-Pfad. Sie benötigen weder FastAPI,
Datenbank, Redis, globale Settings noch Netzwerk.

## Beispiele

Die Dateien unter [`examples/`](examples/) sind reine Dokumentations- und
Test-Fixtures. Sie aktivieren oder migrieren keine bestehende Fachdomäne:

- `example-pois.module.json`: unabhängiges Backend-Modul;
- `example-layer-catalog.module.json`: unabhängiges Frontend-Modul;
- `example-biotopes.module.json`: kombiniertes Modul mit erforderlichem
  `example-layer-catalog` und optionalem `example-statistics`.

Mit den vorhandenen Beispielen ergibt sich die Reihenfolge
`example-layer-catalog`, `example-biotopes`, `example-pois`.
