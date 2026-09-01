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
| `permissions` | `PermissionPort` | hostseitige, fail-closed Policy-Auswertung aus #104 |
| `permission_dependencies` | `PermissionDependencyFactory` | authentifizierte FastAPI-Dependency mit optionalem CSRF für Modulrouten |
| `cache` | `CachePort` | optionaler, modulgebundener Byte-Cache |
| `cache_generations` | `CacheGenerationPort` | Read-Model-Generationen transaktional lesen und erhöhen |
| `public_queries` | `PublicQueryPort` | öffentliche Query-Policy und Limits |
| `map_previews` | `MapPreviewPort` | öffentliche Kartenvorschauen |
| `polygons` | `PolygonQueryPort` | Polygonprojektionen für neutrale `PolygonScope`-IDs |
| `polygon_analytics` | `PolygonAnalyticsPort` | Aggregate für neutrale `PolygonScope`-IDs |
| `statistics` | `StatisticsQueryPort` | kommunale Statistikprojektionen |
| `observability` | `ObservabilityPort` | immer vorhanden; Logger ist an Modul-ID/-Version gebunden |
| `storage` | `StoragePort` | optionaler modulgebundener Blob-Storage |
| `http` | `HttpClientFactoryPort` | in normalen Production-Contexts verfügbarer sicherer Client-Port |
| `scheduler` | `SchedulerPort` | modulgebundene Job-Registry und Job-Definitionen aus #100 |
| `settings` | `ModuleSettingsPort` | typisierte, namespacete Runtime aus #99 |

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

`CachePort.clear()` und `CacheGenerationPort.bump()` haben unterschiedliche
Aufgaben: `clear()` löscht die Keys des aktuellen Moduls. `bump(session,
resources)` erhöht dagegen die Generationen gemeinsam genutzter Lesemodelle über
die vom Aufrufer bereitgestellte Datenbank-Session. Der Bump nimmt vollständig an
dieser caller-owned Transaktion teil und committet niemals implizit. Dadurch können
fachlicher Write und Generation-Bump gemeinsam committed oder gemeinsam
zurückgerollt werden. Doppelte Resource-IDs werden in stabiler Eingabereihenfolge
dedupliziert und pro Aufruf genau einmal erhöht.

### Polygon-Scope

Analysis-Areas-Module besitzen die Zuordnung von Gebieten zu Polygonen. Sie lesen
die primitiven Polygon-IDs aus ihren eigenen Persistenzmodellen und übergeben
diese als unveränderlichen `PolygonScope`. Die Host-Ports kennen weder
`AnalysisArea` noch `PolygonAnalysisArea`; Host-ORM-Modelle werden nicht über die
SDK-Grenze gereicht.

Ein Modul, das zunächst stabile öffentliche Polygon-UUIDs erhält, löst diese über
den versionierten Registry-Service `platform.polygon-identity@1` auf. Dazu fordert
es `PolygonIdentityPort` aus `context.services` an und übergibt einen
`PolygonIdentityRequest`. Der Request akzeptiert höchstens 5.000 echte `UUID`-Werte
und dedupliziert sie stabil in der Reihenfolge ihres ersten Auftretens. Das
`PolygonIdentityResult` liefert erfolgreiche Zuordnungen als immutable
`PolygonIdentity(id, uuid)` in derselben Reihenfolge und unbekannte UUIDs separat in
`missing`; dadurch ist ein Reconcile niemals durch still ausgelassene Werte
mehrdeutig.

Der Host liest dafür ausschließlich seine `user_polygons` und besitzt die Abbildung
von stabiler UUID auf interne ID. Der Consumer besitzt seine Relation, deren
Reconcile und stale cleanup und persistiert diese in seiner caller-owned
Transaktion. Der Resolver ist read-only und führt weder Commit, Rollback noch Flush
aus. Weder ORM-Instanzen noch ein allgemeiner Zugriff auf das Polygon-Repository
werden öffentlich.

### Events, Services, Permissions und Jobs

Der Event-Port ist durch die [Domain-Event- und Outbox-Infrastruktur](domain-events.md)
implementiert. Die [Cross-Module-Service-Registry](service-contracts.md) stellt
versionierte öffentliche Query-/Service-Contracts bereit. Der
[Background-Job-Vertrag](background-jobs.md) registriert stabile Job-IDs, Retry,
Timeout und optionale Intervallanforderungen. Permission-Definitionen stammen aus
dem aktiven Manifest und werden durch die
[Permission-Registry](permissions.md) ausgewertet. Die Service-Auflösung ist kein
allgemeiner Service Locator.

### Modulkonfiguration

Die [namespacete Modulkonfiguration](configuration.md) validiert passive
`ModuleSettingsContribution`-Schemas ausschließlich für aktive Module, bevor deren
Runtimecode geladen wird. Der modulgebundene Port liefert das eigene unveränderliche
Pydantic-Modell. Secrets bleiben backend-private; öffentliche Felder benötigen ein
explizites Opt-in.

### HTTP

Trusted In-Process-Module erhalten `ModuleContext.http` sowohl in der normalen
Web-Runtime als auch in der Domain-Event-Outbox-Worker-Runtime. Sie verwenden
ausschließlich den bestehenden öffentlichen Contract:

```python
if context.http is None:
    raise RuntimeError("Host HTTP port is required")
async with context.http.create(
    service_name="wikidata",
    base_url="https://www.wikidata.org",
) as client:
    response = await client.request("GET", "/w/api.php", params={"format": "json"})
```

Der Async-Context-Manager besitzt den vollständigen Client-Lifecycle und schließt
Transport sowie Connection Pool auch bei Transport- oder Timeout-Exceptions. Der
Production-Adapter verwendet einen Host-kontrollierten 10-Sekunden-Timeout, einen
begrenzten Pool mit vier Verbindungen und zwei Keep-Alive-Verbindungen, einen festen
User-Agent und keine automatischen Redirects. Er führt selbst keine Retries aus;
Retry-Ownership bleibt beim Consumer beziehungsweise beim bestehenden Job-Vertrag.

Der Adapter übernimmt keine Authorization-, Cookie-, Proxy- oder internen
Service-Token aus dem Host-Prozess. Insbesondere wird die `httpx`-Umgebungsauflösung
für Proxy-/Credential-Konfiguration deaktiviert. Explizite fachliche Header bleiben
Aufgabe des trusted Moduls. Base- und Request-URLs müssen HTTP(S) verwenden und
dürfen keine eingebetteten Zugangsdaten enthalten.

`service_name` ist ein validierter, niedrig-kardinaler Provider-Key. Bestehende
externe Request-Metriken verwenden ausschließlich diesen Key, die HTTP-Methode und
Outcome/Fehlerklasse; vollständige URLs oder Queryparameter werden nicht als Label
verwendet. Der SDK-Port gibt keinen konkreten `httpx.AsyncClient` an Module weiter.

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

Die Capability- und Legacy-Import-Zuordnung für die mit SDK 1.9 ergänzten Ports
steht in [Öffentliche Backend-Service-Ports](backend-service-ports.md).

`MODULE_SDK_VERSION` ist eine SemVer-Version und unabhängig von Release-SHA und
Host-API-Version. Der Context wurde unter SDK `1.0.0` eingeführt. Die additive
Event-/Outbox-API aus #96 erhöhte die SDK-Version auf `1.1.0`. Die additiven
Persistence-Contracts und der produktive Datenbank-Session-Adapter aus #97 erhöhten
sie auf `1.2.0`. Die additive, versionierte Service-Registry aus #98 erhöht sie auf
`1.3.0`. Die additive typisierte Settings-API und `ModuleSettingsContribution` aus
#99 erhöhen sie auf `1.4.0`; der minimale `DomainEvent`-Contract aus 1.0 und die
#94-Proxys bleiben kompatibel. Die additive Job-Definition, Registry und Ausführung
aus #100 erhöhen sie auf `1.5.0`; die einfache Scheduler-Registrierung aus #95
bleibt als Kompatibilitätsform erhalten.
Die additive Permission-Definition und hostseitige Registry aus #104 erhöhen die
SDK-Version auf `1.6.0`; die bestehende `PermissionPort.is_allowed()`-Signatur
bleibt kompatibel.
Die additive `PermissionDependencyFactory` erhöht die SDK-Version auf `1.7.0`. Sie
gibt Modulrouten ausschließlich eine minimale `ModulePrincipal`-ID und adaptiert die
bestehende Host-Authentifizierung, CSRF-Prüfung und Permission Engine, ohne User- oder
Auth-Interna Teil des SDK zu machen.
Die additive, optionale `ModuleMigrationSource.adopted_revisions`-Metadata erhöht
die SDK-Version auf `1.8.0`. Bestehende Module erhalten standardmäßig eine leere
unveränderliche Menge und müssen ihren Migration Contract nicht ändern.
Die additiven öffentlichen Backend-Service-Ports für Cache-Generationen,
Public-Query-Schutz, Kartenvorschauen, Polygonabfragen und -aggregate,
Kommunalstatistik erhöhen die SDK-Version auf `1.9.0`.
Die additive transaktionale `CacheGenerationPort.bump()`-Methode erhöht die
SDK-Version auf `1.10.0`. `current()` bleibt unverändert; `bump()` verwendet die
Caller-Session, öffnet keine zweite Transaktion und committet nicht selbst.
Der additive, über die Service-Registry aufgelöste
[`OsmSnapshotQueryPort`](osm-public-contract.md) und der öffentliche
`osm.postprocessing-completed`-Eventvertrag erhöhen die SDK-Version auf `1.11.0`.
Beide Verträge geben weder Host-ORM-Modelle noch modulbezogene Fachableitungen aus.
Der additive [`PolygonSpatialMatchPort`](polygon-assignment-contract.md) erhöht die
SDK-Version auf `1.12.0`. Er gleicht immutable Area-Geometrien rein lesend mit
Host-eigenen Polygonen ab und liefert stabile Polygon-UUIDs sowie räumliche
Match-Metriken. Domänenspezifische Relation und Persistenz bleiben beim Consumer.
Die Production-Verdrahtung des bereits seit SDK 1.9 vorhandenen
`HttpClientFactoryPort` ändert den öffentlichen Contract nicht; die SDK-Version
bleibt deshalb zunächst `1.12.0`.
Der additive, über die Service-Registry aufgelöste `PolygonIdentityPort` erhöht die
SDK-Version auf `1.13.0`. Er löst stabile öffentliche Polygon-UUIDs begrenzt und
deterministisch in die bereits von `PolygonScope` und bestehenden Relationsschemas
benötigte Host-Identität auf, ohne ORM-Typen oder Transaktionsownership offenzulegen.
SDK `1.14.0` korrigiert die Statistics-Grenze: Consumer übergeben eine vollständig
aufgelöste `StatisticsSelection` aus Requested-, Target- und Municipality-Referenz.
Damit entscheidet die owning Fachdomäne über Hierarchie und Vererbung; die
Kommunalstatistik liest ausschließlich ihre eigene Gebietszuordnung und kennt weder
fremde Tabellen noch Slug- oder Parent-Semantik. Module, die den Statistics-Port
verwenden, müssen deshalb mindestens SDK 1.14 deklarieren.
Alle Ports sind optional; bestehende Module und ihre Context-Konstruktion bleiben
damit rückwärtskompatibel.

- **MAJOR:** Entfernen oder Umbenennen öffentlicher Methoden, inkompatible Änderungen
  an vorhandener Semantik oder eine inkompatible Context-Struktur.
- **MINOR:** additive optionale Ports, zusätzliche Capability-APIs oder neue
  kompatible Helper.
- **PATCH:** Fehlerkorrekturen und Typing-Präzisierungen ohne Runtime-Bruch.

Deprecations werden dokumentiert und mindestens über einen angekündigten
Migrationszeitraum parallel unterstützt. Ein Git-SHA ist keine SDK-Version.
