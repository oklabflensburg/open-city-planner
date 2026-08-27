# Reviewed Community Modules entwickeln und prüfen

Ein Reviewed Community Module läuft mit den Rechten des Open-City-Planner-
Hostprozesses. Installation setzt Code-Review und Vertrauen voraus. Die
Modularchitektur sandboxed weder Python- noch Frontend-Code.

## Was das praktisch bedeutet

`ModuleContext`, Capabilities, Permissions, Settings- und Persistence-Ownership
sind die offiziell unterstützten Verträge. Sie machen Anforderungen sichtbar und
prüfbar, verhindern aber nicht, dass kompromittierter Python-Code technisch Dateien,
Prozessumgebung, Netzwerk oder Datenbankzugänge des Hosts verwendet. Frontend-Code
läuft im gemeinsamen Nuxt-/Browser-Kontext.

Wenn der Code nicht in diesem Umfang vertraut werden kann, darf er nicht als
In-Process-Modul geliefert werden. Verwende stattdessen eine Remote Integration mit
einer stabilen API und den in der
[Trust-ADR](../architecture/adr-module-trust-model.md) beschriebenen Grenzen.

## Review-Paket

Stelle für einen Installationsreview mindestens bereit:

- öffentlich nachvollziehbare Quelle, Repository und Maintainer;
- exakte Modul-, Distribution- und Dependency-Versionen;
- vollständigen Commit-SHA sowie SHA-256-Checksumme/Package-Integrity;
- Lizenz und gelockten Dependency-Satz;
- Manifest mit Capabilities, Permissions und Dependencies;
- Settings-Schema mit markierten Secrets und dokumentierten Endpoints;
- Liste aller Datei-, Netzwerk-, Telemetrie- und Browserzugriffe;
- Persistence-Schema, Tabellen und sämtliche Migrationen;
- Jobs, Lifecycle-Hooks, API-Router und Frontend-Contributions;
- SBOM sowie Ergebnisse der Dependency-, Secret- und SAST-Scans;
- Disable-, Datenhaltungs- und Incident-Verhalten.

Der freigegebene Datensatz wird vom Host verwaltet, nicht im fremden Manifest. Eine
abweichende Paketversion, unbekannte Integrität oder ein fehlender Review-Grant
blockiert den Entry Point vor dem Import.

## Offizielle Implementierungswege

- Konfiguration und Secrets: typisiertes `ModuleContext.settings`, niemals globale
  Settings oder selbst gelesene `.env`-Dateien;
- Datenbank: `ModuleContext.database`, eigene Tabellen und eigene Repositories;
- andere Module: öffentliche Service-/Event-Contracts, keine internen Imports;
- Netzwerk: hostseitiger HTTP-Port, deklarierte Hosts, Timeouts, Limits, sichere
  Redirects und datensparsame Observability;
- Jobs: `ModuleContext.scheduler`, keine versteckten In-Process-Timer;
- Benutzerrechte: registrierte Permissions und serverseitige Prüfung;
- UI: deklarierte Contributions innerhalb der vorgesehenen Slots.

Diese Regeln begrenzen den unterstützten Vertrag und ermöglichen Reviews. Sie sind
keine OS-, PostgreSQL-, Python- oder Browser-Sandbox.
