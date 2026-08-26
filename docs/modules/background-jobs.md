# Modulare Background Jobs

Die Job-Infrastruktur aus #100 setzt die Job-Grenze aus
[ADR #92](../architecture/adr-modular-host-and-module-boundaries.md) um. Der Host
besitzt Registry, Ausführung und Telemetrie. Ein Modul besitzt stabile Job-IDs,
Handler, Retry-/Timeout-Policy, fachliche Idempotenz und eine optionale
Schedule-Anforderung.

## Bestehende Background-Flows

Die Einführung ersetzt die vorhandenen Worker nicht flächendeckend. Das Audit der
Legacy-Basis ergibt:

| Flow | Start und Process Owner | Retry / Timeout | Observability | Status in #100 |
| --- | --- | --- | --- | --- |
| Domain-Event-Outbox | CLI `process_domain_event_outbox`, minütlicher systemd-Timer | persistente Delivery-Retries, Dead Letter und verwaiste DB-Claims | Event-Spans, Logs, Event-/Outbox- und Jobmetriken | Pilot über `host-events.outbox-dispatch` |
| Social/Mastodon | CLI `publish_social_outbox`, optionaler minütlicher Timer | persistenter Provider-Backoff, Max Attempts, HTTP-/Screenshot-Timeouts | `observed_job`, Outbox- und Providermetriken | unverändert |
| E-Mail-Outbox | CLI `process_email_outbox`, minütlicher Timer | persistente geplante Retries, Max Attempts und terminale Fehler | `observed_job`, Outbox-Metriken und Auditlog | unverändert |
| Polygon-Outbox | CLI `process_polygon_outbox`; kein verwalteter Ansible-Timer in der aktuellen Rolle | acht Versuche, exponentieller Backoff, Dead Letter und stale Claim Recovery | Outbox-Metriken und Logs | unverändert; neue Events nutzen bereits die gemeinsame Event-Outbox |
| Notification Cleanup | manuelle CLI `cleanup_notifications` | kein eigener Retry-/Timeout-Contract | Abschlusslog und CLI-Ergebnis | unverändert |
| Cache Maintenance | manuelle CLIs für Status, Clear und Versions-Bump | kein eigener Retry-/Timeout-Contract | CLI-Ergebnis und Redis-Metriken | unverändert |
| OSM/Open-Data | systemd-Timer startet das bestehende Sync-Skript; Postprocessing nutzt `observed_job` | systemd-Neustart beim nächsten Intervall, Provider-/DB-Timeouts im jeweiligen Schritt | Job-, OSM-, Provider- und DB-Metriken sowie Fortschrittslogs | unverändert |
| Statistik-Refresh | CLI `import_flensburg_statistics`, wöchentlicher systemd-Timer | kein unmittelbarer Job-Retry; nächster Timerlauf, HTTP-Client-Timeouts | `observed_job` und Importbericht | unverändert |
| Map Preview | synchron auf Cache Miss im API-Prozess; separater Renderer-Service | Renderer-HTTP-Timeout; kein Background-Schedule | Provider-Telemetrie und Cache | kein Job und unverändert |

Es existiert keine zentrale Queue, kein Broker und kein produktiver In-Process-
Scheduler. GitHub-Actions-Cronjobs betreffen Repositoryprüfungen und sind keine
fachlichen Runtime-Jobs.

## Öffentlicher SDK-Contract

Module registrieren während `module.register(context)` eine `JobDefinition` über
den bereits in #95 eingeführten `context.scheduler`-Port:

```python
from app.platform.modules.sdk import JobDefinition, JobSchedule, ModuleContext, RetryPolicy


async def refresh(context: ModuleContext) -> None:
    assert context.settings is not None
    assert context.database is not None
    settings = context.settings.require(StatisticsSettings)
    async with context.database.session() as session:
        await refresh_statistics(session, settings)


def register(context: ModuleContext) -> None:
    assert context.scheduler is not None
    context.scheduler.register(
        JobDefinition(
            job_id="refresh",
            handler=refresh,
            retry=RetryPolicy(
                max_attempts=3,
                initial_delay_seconds=5,
                backoff_multiplier=2,
                max_delay_seconds=60,
            ),
            timeout_seconds=120,
            schedule=JobSchedule(interval_seconds=86_400),
        )
    )
```

Das Modul deklariert nur den stabilen lokalen Jobnamen. Der gebundene Port leitet
daraus deterministisch `<module-id>.<job-name>` ab; im Beispiel entsteht
`statistics.refresh`. Vollqualifizierte IDs bleiben kompatibel, müssen aber dem
registrierenden Modul gehören. Function-Namen sind keine Job-Identität. Die Registry
hält den owning `module_id`, den vollständigen Descriptor und den gebundenen
`ModuleContext`. Nur aktivierte Module werden instanziiert und können Jobs
registrieren. Nach Abschluss aller `register()`-Hooks wird die Registry versiegelt.

Die einfache Form `context.scheduler.register("refresh", handler)` aus dem frühen
#95-Port bleibt kompatibel und wird ebenfalls zum Modulnamespace qualifiziert. Neue
Module verwenden `JobDefinition`, um Retry, Timeout und Schedule explizit zu machen.

## Ausführung, Retry und Timeout

`JobRunner.run(job_id)` erzeugt pro Aufruf eine UUID-Run-ID und übergibt dem Handler
den owning `ModuleContext`. Damit verwendet Jobcode Settings aus #99, Services aus
#98, Datenbankprimitives aus #97 und Events aus #96, ohne globale Host-Settings,
Session-Factories oder Fachimporte anderer Module.

Ein Timeout zählt als fehlgeschlagener Versuch. Nach jedem fehlgeschlagenen Versuch
steigt der Retry-Zähler; der nächste Abstand ist durch initiale Verzögerung,
Multiplikator und Maximalverzögerung begrenzt. Nach `max_attempts` endet der Lauf mit
`JobExecutionError` beziehungsweise `JobTimeoutError`. Es gibt keine endlose
Wiederholung. Andere Jobs und die Module-Runtime bleiben von diesem Fehler
unberührt.

Handler müssen retry-sicher sein: Ein Versuch kann nach einem externen Side-Effect
scheitern. Deduplizierung, Unique Constraints oder providerseitige Idempotency-Keys
bleiben deshalb fachliche Verantwortung. Der Job-Runner ersetzt nicht die
persistente Retry-/Dead-Letter-Semantik einer Outbox.

## Scheduling und Parallelität

V1 unterstützt eine optionale, validierte Intervallanforderung in positiven ganzen
Sekunden. Das Modul beschreibt damit den fachlich gewünschten Rhythmus; der Host
entscheidet über die technische Umsetzung. Produktionsseitig bleibt systemd der
einzige Scheduler. Es wird kein zweiter In-Process-Timer gestartet und keine
verteilte Lock-Infrastruktur behauptet.

`allow_concurrent_runs` ist standardmäßig `False`. Innerhalb eines Prozesses
serialisiert der Runner gleichzeitige Aufrufe derselben Job-ID. systemd beziehungsweise
eine spätere technische Scheduler-Ebene muss zusätzlich Single-Owner sicherstellen,
wenn mehrere Prozesse oder Hosts denselben Schedule sehen. Bereits vorhandenes
DB-Claiming, etwa `FOR UPDATE SKIP LOCKED` in Outboxes, bleibt erhalten.

## Observability

Strukturierte Logs verwenden `module_id`, `job_id`, `job_run_id`, `job_attempt`,
`job_phase` und die gemessene Laufzeit. Unterstützte Phasen sind `scheduled`,
`started`, `succeeded`, `failed`, `retry_scheduled` und `timed_out`. Run-IDs und
Fehlerdetails werden niemals als Metriklabel verwendet.

Metriken:

- `module_job_runs_total{module_id,job_id,result}`
- `module_job_failures_total{module_id,job_id}`
- `module_job_retries_total{module_id,job_id}`
- `module_job_duration_seconds{module_id,job_id,result}`
- `module_job_last_success_timestamp_seconds{module_id,job_id}`

Modul- und Job-IDs stammen ausschließlich aus deploy-time registriertem Code und
sind damit begrenzt. Der letzte Erfolg ist in V1 eine In-Memory-Gauge; Job-Historie
wird nicht in einer neuen Datenbanktabelle gespeichert.

## Pilot und Deployment-Kompatibilität

Der bestehende Domain-Event-Outbox-Worker registriert vor dem Versiegeln der Runtime
den Legacy-Adapter `host-events.outbox-dispatch` und führt ihn über `JobRunner` aus.
Die injizierte Handler-Funktion importiert weder Host-Settings noch globale DB- oder
Cache-Module. Der Composition-Root injiziert die bestehende Session-Factory, solange
der Legacy-Worker noch eigene Commit-Grenzen für Claims und Deliveries benötigt.

Der bestehende Befehl bleibt unverändert:

```bash
python -m app.cli.process_domain_event_outbox --limit 50
```

Auch `stadtplaner-domain-event-outbox.service` und sein minütlicher Timer bleiben
unverändert. Der Pilot verwendet `RetryPolicy(max_attempts=1)`, weil die Outbox ihre
fünf persistierten Zustellversuche bereits selbst kontrolliert. Rollback bedeutet
daher lediglich, den vorherigen Release auszuführen; Datenmodell und Deployment-
Units wurden nicht verändert.

## Scope

#100 führt weder Celery, Kafka, RabbitMQ, Redis Queue, APScheduler, Airflow, Temporal
noch eine Workflow-DAG oder Job-History-Tabelle ein. Domain Events bleiben Events;
Jobs ersetzen sie nicht. Weitere Legacy-Worker werden erst in eigenen fachlichen
Migrationen übernommen.
