# Öffentliches Backend-Module-SDK

Das öffentliche Backend-SDK setzt die Host-/Modulgrenze aus
[ADR #92](../architecture/adr-modular-host-and-module-boundaries.md) um. Es baut auf
dem [Manifest-V1-Contract](module-manifest-v1.md) und der
[Backend-Module-Runtime](backend-module-runtime.md) auf. Modulcode importiert
Plattformverträge ausschließlich aus:

```python
app.platform.modules.sdk
```

`app.platform.modules.runtime`, `discovery`, `context`, `contracts` und weitere
Hostdateien sind Implementierungsdetails der Composition Root. Bestehende Re-Exports
unter `app.platform.modules` bleiben für die junge #94-Integration kompatibel, sind
aber kein neuer Modul-SDK-Importpfad.

## ModuleContext

Der Host erzeugt für jedes validierte Modul einen eigenen, unveränderlichen
`ModuleContext`. `module_id` und `module_version` stammen aus dem bereits geprüften
Manifest. Ein Modul kann weder den Context eines anderen Moduls anfordern noch seine
gebundene Identität regulär verändern.

```python
from fastapi import APIRouter

from app.platform.modules.sdk import ModuleContext, ModuleManifestV1


class ExampleModule:
    manifest: ModuleManifestV1

    def register(self, context: ModuleContext) -> None:
        router = APIRouter()

        @router.get("/ping")
        async def ping() -> dict[str, str]:
            context.logger.info("Ping request handled")
            return {"status": "ok"}

        context.api.include_router(router, prefix="/api/v1/example")
```

`register()` deklariert Beiträge und führt keine Netzwerk-, Worker- oder anderen
externen Startup-Side-Effects aus. `context.api` registriert Router;
`context.lifecycle` registriert asynchrone Startup-/Shutdown-Hooks. Beide Registrare
werden nach `register()` geschlossen. Der Context selbst kann von Hooks oder
Request-Handlern weiter referenziert werden; seine Host-Service-Ports bleiben
unverändert gebunden.

Die direkten Methoden `context.include_router()` und `context.add_lifecycle()` sind
Kompatibilitäts-Proxys für #94. Neuer Modulcode verwendet die expliziten
Sub-Interfaces `context.api` und `context.lifecycle`.

## Öffentliche Ports

| Context-Feld | Contract | Status nach #95 |
|---|---|---|
| `api` | `ApiRegistrar` | durch die Runtime implementiert |
| `lifecycle` | `LifecycleRegistrar` | durch die Runtime implementiert |
| `database` | `DatabaseSessionProvider` | transaktionaler Hostadapter aus #97 |
| `events` | `EventBusPort` | In-Process Dispatch und transaktionale Outbox aus #96 |
| `services` | `ServiceRegistryPort` | runtime-skopierte Cross-Module-Registry aus #98 |
| `permissions` | `PermissionPort` | optionaler Port; Policy Engine folgt in #104 |
| `cache` | `CachePort` | optionaler, modulgebundener Byte-Cache |
| `observability` | `ObservabilityPort` | immer vorhanden; Logger ist an Modul-ID/-Version gebunden |
| `storage` | `StoragePort` | optionaler modulgebundener Blob-Storage |
| `http` | `HttpClientFactoryPort` | optionaler sicherer Client-Port |
| `scheduler` | `SchedulerPort` | optionaler Port; Job Runtime folgt in #100 |
| `settings` | `ModuleSettingsPort` | optionaler, namespaced Port; Runtime folgt in #99 |

Ein optionaler Port mit dem Wert `None` ist nicht durch den Host bereitgestellt. Das
ist ein definierter Zustand und kein stiller Fallback auf Host-Interna. Ein Modul
darf deshalb nicht ersatzweise `app.db`, `app.cache`, `app.services`, `app.core` oder
andere interne Hostpakete importieren. Benötigte Ports müssen vor ihrer Verwendung
explizit geprüft beziehungsweise künftig als Modulanforderung deklariert werden.

### Datenbank

`DatabaseSessionProvider.session()` liefert einen asynchronen Context Manager mit
einer SQLAlchemy-`AsyncSession`. SQLAlchemy ist bewusst Teil dieses stabilen Ports,
weil es eine Kerntechnologie des Hosts ist und eine künstliche parallele ORM-
Abstraktion keinen Mehrwert bietet. Fachliche ORM-Modelle, globale Session Factories,
Engines und `app.db.session` sind dagegen nicht Teil des SDK. Ownership und modulare
Migrationen sind im
[Datenbank- und Migrationsvertrag](database-and-migrations.md) definiert.
`ModulePersistenceContribution` hängt Metadata und eine optionale installierte
`ModuleMigrationSource` passiv an die `ModuleDefinition`; Alembic muss dafür weder
`register()` ausführen noch Modul-Interna durchsuchen.

### Cache und Storage

Cache-Schlüssel und Storage-Keys gelten relativ zum aktuellen Modul; konkrete
Adapter müssen sie entsprechend isolieren. Cache-TTLs sind positive ganze Sekunden.
Die Ports machen keine Redis-, Dateisystem- oder Cloud-SDK-Typen öffentlich.

### Events, Services, Permissions und Jobs

Der Event-Port ist durch die [Domain-Event- und Outbox-Infrastruktur](domain-events.md)
implementiert. Die [Cross-Module-Service-Registry](service-contracts.md) stellt
versionierte öffentliche Query-/Service-Contracts bereit. Permission Policy und
Job-Ausführung bleiben ihren Folge-Issues vorbehalten. Die Service-Auflösung ist
kein allgemeiner Service Locator.

### HTTP

Module definieren fachliche Zielpfade. Der Hostadapter besitzt Timeouts, User-Agent,
Connection Pooling, Observability und Sicherheitsregeln wie SSRF-Schutz. Der Port
gibt keinen konkreten `httpx.AsyncClient` an Module weiter.

### Observability

`context.logger` ist ein Python-`LoggerAdapter`, der `module_id` und
`module_version` automatisch als strukturierte Felder trägt. Metrics und Tracing
verwenden kleine vendor-neutrale Ports. Metrikattribute müssen stabil und
niedrig-kardinal bleiben; Nutzungs-, Request- oder Suchwerte sind keine Labels.

## Infrastrukturfreie Tests

`app.platform.modules.testing` stellt `create_test_module_context()` sowie kleine
Fakes für Cache, Events, Services, Permissions, Metrics, Tracing, Storage, HTTP,
Scheduler und Settings bereit. Sie verwenden weder Datenbank noch Redis, Netzwerk
oder Dateisystem. Der Datenbankport bleibt im Standard-Testcontext bewusst `None`;
datenbankbezogener Modulcode injiziert einen gezielten Session-Fake oder testet gegen
eine ausdrücklich bereitgestellte isolierte Datenbank.

## Vertrauen und Importregeln

Das SDK ist eine Architekturgrenze, keine Sandbox. Installierte Module bleiben
vertrauenswürdiger In-Process-Code. Ein fokussierter Architekturtest stellt sicher,
dass das SDK keine Fachtypen oder Host-Interna importiert und das Runtime-Fixture
unter `app.*` ausschließlich den öffentlichen SDK-Pfad verwendet.

## SDK-Versionierung

`MODULE_SDK_VERSION` ist eine SemVer-Version und unabhängig von Release-SHA und
Host-API-Version. Der Context wurde unter SDK `1.0.0` eingeführt. Die additive
Event-/Outbox-API aus #96 erhöhte die SDK-Version auf `1.1.0`. Die additiven
Persistence-Contracts und der produktive Datenbank-Session-Adapter aus #97 erhöhten
sie auf `1.2.0`. Die additive, versionierte Service-Registry aus #98 erhöht sie auf
`1.3.0`; der minimale `DomainEvent`-Contract aus 1.0 und die #94-Proxys bleiben
kompatibel.

- **MAJOR:** Entfernen oder Umbenennen öffentlicher Methoden, inkompatible Änderungen
  an vorhandener Semantik oder eine inkompatible Context-Struktur.
- **MINOR:** additive optionale Ports, zusätzliche Capability-APIs oder neue
  kompatible Helper.
- **PATCH:** Fehlerkorrekturen und Typing-Präzisierungen ohne Runtime-Bruch.

Deprecations werden dokumentiert und mindestens über einen angekündigten
Migrationszeitraum parallel unterstützt. Ein Git-SHA ist keine SDK-Version.
