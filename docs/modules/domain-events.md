# Domain Events und transaktionale Outbox

Die Host-Infrastruktur aus #96 verbindet Module und schrittweise migrierte
Legacy-Domänen über stabile Events. Producer kennen keine Consumer. Fachliche
Eventtypen gehören dem produzierenden Modul; der Host besitzt nur Envelope,
Subscriber-Registry, Outbox, Zustellung und Telemetrie.

## Öffentlicher Vertrag

Module importieren `EventEnvelope`, `SerializableDomainEvent` und `EventBusPort`
ausschließlich aus `app.platform.modules.sdk`. Ein typisiertes Event nennt einen
stabilen Namen, eine positive Version und serialisiert seinen Payload explizit:

```python
from dataclasses import dataclass
from typing import ClassVar
from uuid import UUID

from app.platform.modules.sdk import JsonValue


@dataclass(frozen=True, slots=True)
class PolygonCreated:
    polygon_id: UUID
    event_name: ClassVar[str] = "polygons.created"
    event_version: ClassVar[int] = 1

    def to_payload(self) -> dict[str, JsonValue]:
        return {"polygon_id": str(self.polygon_id)}
```

Namen verwenden `<module-id>.<event-name>` und bleiben stabil. Eine inkompatible
Payload-Änderung erhöht `event_version`; additive kompatible Felder dürfen dieselbe
Version behalten. Consumer deklarieren ihre unterstützten Versionen ausdrücklich.
UUIDs und Zeitwerte werden vom Producer als Strings standardisiert. Der SDK-Validator
akzeptiert ausschließlich JSON-Werte und lehnt Python-Objekte, ORM-Instanzen,
`datetime`, `UUID`, nicht endliche Zahlen sowie nicht-stringbasierte Objekt-Keys ab.

Der Envelope enthält eine global eindeutige Event-UUID, UTC-Zeitpunkt,
`correlation_id`, `causation_id`, begrenzten Trace-Kontext, Producer-ID und Payload.
Die Event-ID ist unabhängig von fachlichen Tabellen-Primärschlüsseln und dient als
stabile Idempotenz- und Debugging-Identität.

Der minimale `DomainEvent`-Contract mit `event_type` aus SDK 1.0 bleibt kompatibel;
solche Events erhalten einen leeren Payload. Neuer Code verwendet den explizit
serialisierbaren Contract.

## Publishing und Registrierung

Direkte In-Process-Zustellung propagiert Handler-Fehler an den Publisher:

```python
await context.events.publish(event)
```

Sie eignet sich nur, wenn Publisher und Handler dieselbe unmittelbare
Fehlersemantik wünschen. Es gibt keine persistente Retry-Garantie.

Fachänderungen verwenden die transaktionale Variante mit der bereits vorhandenen
Session:

```python
await context.events.publish_after_commit(event, session=session)
await session.commit()
```

Der Publisher führt niemals selbst `commit()` aus. Fachänderung und Outbox-Eintrag
werden daher atomar committed oder gemeinsam zurückgerollt. Vor dem Commit findet
keine Zustellung statt.

Subscriber werden während `module.register(context)` mit deploy-stabiler,
modulgebundener Handler-ID registriert:

```python
context.events.subscribe(
    "polygons.created",
    handler_id="notifications.polygon-created",
    versions=frozenset({1}),
    handler=handle_polygon_created,
)
```

Die Reihenfolge entspricht deterministisch der Bootstrap-Reihenfolge. Doppelte
Handler-IDs werden abgelehnt. Nach dem Bootstrap wird die Registry geschlossen;
dynamische Subscriber aus Nutzereingaben sind nicht zulässig. Existiert kein
Subscriber, wird ein persistiertes Event ohne Fehler abgeschlossen. Existieren
Subscriber, aber unterstützen sie die Version nicht, entstehen sichtbare
Dead-Letter-Deliveries statt einer stillen Fehlinterpretation.

## Outbox und Delivery

`domain_event_outbox` speichert den fachneutralen Envelope. `event_delivery`
speichert den Zustand separat für jede Kombination aus `event_id` und `handler_id`;
ein Unique Constraint bildet den standardisierten Deduplizierungsschlüssel.

Der Dispatcher:

1. materialisiert Deliveries aus der deploy-time Subscriber-Registry;
2. claimt fällige Deliveries mit PostgreSQL `FOR UPDATE SKIP LOCKED`;
3. committed Worker-ID, Lock-Zeitpunkt und Versuch vor dem Handler-Aufruf;
4. markiert Erfolg oder plant einen Retry;
5. verschiebt die Delivery nach dem letzten Versuch in `DEAD_LETTER`;
6. schließt das Event ab, sobald alle Handler terminal sind.

Ein zehn Minuten alter `PROCESSING`-Lock gilt als verwaist und wird wieder
freigegeben. Mehrere App-Instanzen können dadurch parallel arbeiten, ohne dieselbe
Delivery gleichzeitig zu claimen. Zwischen unabhängigen Events besteht keine globale
Ordering-Garantie. Benötigt ein Consumer fachliche Reihenfolge, muss sein Contract
eine Aggregate-/Datenversion transportieren und prüfen.

Die Standard-Retry-Policy umfasst fünf Versuche mit 30 Sekunden, zwei Minuten, zehn
Minuten und einer Stunde Abstand. Fehler werden pro Handler isoliert. Ist Handler A
erfolgreich und Handler B fehlerhaft, wird ausschließlich B erneut ausgeführt.

## At-least-once und Idempotenz

Die Zustellung ist **at least once**. Ein Prozess kann nach einem fachlichen
Side-Effect und vor dem erfolgreichen Delivery-Commit ausfallen. Deshalb müssen
Handler zusätzlich fachlich idempotent sein, beispielsweise durch einen
Unique Constraint, eine providerseitige Idempotency-ID oder eine fachliche
Deduplizierungsregel. Eine bereits erfolgreich persistierte Delivery wird bei einem
Dispatcher-Neustart nicht erneut ausgeführt.

Handler-Fehler können die ursprüngliche Producer-Transaktion nicht zurückrollen: Sie
ist vor dem Claim bereits erfolgreich committed. Fehler und Versuche bleiben pro
Handler sichtbar. Dead Letter ist ein operatorisch zu prüfender Zustand; #96 führt
noch keine Admin-Oberfläche ein.

## Correlation, Tracing und Observability

Der Host übernimmt die vorhandene Request-ID als `correlation_id`, sofern der
Producer keine explizite ID setzt. Folgeevents können die auslösende Event-ID als
`causation_id` angeben. Vorhandene Trace-/Span-IDs werden im Envelope erhalten. Der
Dispatcher erzeugt mit der bestehenden OpenTelemetry-Infrastruktur einen
`domain_event.dispatch`-Span mit Eventname, Version, Handler und Versuch.

Strukturierte Logs verwenden die Phasen `queued`, `claimed`, `dispatch_started`,
`dispatch_succeeded`, `dispatch_failed`, `retry_scheduled` und `dead_lettered`. Sie
enthalten Event-ID, Name, Version, Producer, Handler, Versuch und Correlation-ID.

Metriken:

- `event_outbox_pending`
- `event_outbox_oldest_age_seconds`
- `event_dispatch_total`
- `event_dispatch_failures_total`
- `event_dead_letter_total`
- `event_handler_duration_seconds`

Event- und Handlernamen stammen ausschließlich aus deploy-time Code. Event-ID,
Correlation-ID und andere hochkardinale Werte sind keine Labels. Queue Lag ist das
Alter des ältesten noch nicht vollständig verarbeiteten Events.

## Betrieb und Retention

`python -m app.cli.process_domain_event_outbox --limit 50` führt einen begrenzten
Dispatch-Lauf aus. Das Deployment startet ihn minütlich über
`stadtplaner-domain-event-outbox.timer`; es wird kein allgemeines Scheduler- oder
Job-Framework eingeführt.

Erfolgreich oder endgültig abgeschlossene Events sollen nach einer betrieblich
festgelegten Diagnosefrist, empfohlen 30 Tage, gelöscht werden. Dafür existiert der
explizite Service-Hook `delete_processed_events_before`; automatische Planung bleibt
#100 vorbehalten. Dead-Letter-Details müssen vor einer Bereinigung ausgewertet sein.

## Sicherheit und Datenschutz

Payloads bleiben minimal und enthalten vorzugsweise IDs. Sie dürfen keine Passwörter,
Hashes, Access-/Refresh-Tokens, OAuth-/MFA-Secrets, Sessiondaten oder komplette
ORM-Objekte enthalten. Personenbezogene Felder werden nur aufgenommen, wenn der
Eventvertrag und die Aufbewahrung fachlich erforderlich sind. Handler-Fehlertexte
dürfen ebenfalls keine Secrets enthalten.

## Pilot und Migration bestehender Outboxes

Neue Polygon-Create-/Update-/Delete-Events bilden den Legacy-Pilot. Polygon-Code
publiziert nur producer-owned Events. Separat registrierte Adapter übernehmen
Adress-Enrichment, Notifications und das Abbrechen offener Social-Publikationen; der
Producer importiert diese Consumer nicht.

Die bestehenden Tabellen werden bewusst nicht entfernt:

1. Die gemeinsame Host-Infrastruktur läuft parallel zu `polygon_outbox`,
   `email_outbox` und `social_publication_outbox`.
2. Neue Polygon-Mutationen verwenden die gemeinsame Outbox. Bereits vorhandene
   `polygon_outbox`-Datensätze können weiter mit dem bisherigen Worker abgearbeitet
   werden.
3. E-Mail- und Mastodon-Flows werden in separaten Änderungen migriert, nachdem der
   Pilot betrieblich verifiziert ist.
4. Alte Tabellen und Services werden erst gelöscht, wenn keine Producer, Consumer
   oder ausstehenden Records mehr existieren.

Ein Rollback kann neue Polygon-Publisher wieder auf den weiterhin vorhandenen
Legacy-Writer umstellen. Die Migration `20260825_0034` erstellt ausschließlich neue
Host-Tabellen und verändert keine fachlichen oder bestehenden Outbox-Tabellen.

## Abgrenzung zu Event Sourcing

Die Outbox ist ein Integrations- und Zustellungsmechanismus, kein Event Store. Der
Anwendungszustand wird nicht aus diesen Events rekonstruiert. #96 führt weder CQRS,
Aggregate-Streams, ein Replay-Framework noch Kafka, RabbitMQ, Celery oder eine
verteilte Event-Plattform ein.
