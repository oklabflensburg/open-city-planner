# Third-Party-Module entwickeln und prüfen

Ein installiertes Third-Party-Modul läuft mit den Rechten des Open-City-Planner-
Hostprozesses beziehungsweise im gemeinsamen Browser-Kontext. In-Process-Code muss
daher vor Installation geprüft und anschließend wie Trusted Code behandelt werden.
Die Modularchitektur ist keine Sandbox.

## Installationsgrenze

Ein Paket erreicht Discovery und Runtime ausschließlich über den kontrollierten
Installer-/Deploymentpfad:

```text
Package
  -> Installer
  -> Verify/Review
  -> modules.lock
  -> Backend/Frontend artifacts installed
  -> Discovery
  -> Runtime
```

Der Installer und `modules.lock` werden in #173 umgesetzt; das überprüfbare OCP-
Bundle folgt in #174. Die heutige Entry-Point-Discovery findet lediglich bereits
installierte Distributionen. Sie installiert nichts, lädt nichts aus dem Netz und
ist kein zweites Review-Gate.

## Review-Paket

Für den Installationsreview sind mindestens bereitzustellen:

- öffentlich nachvollziehbare Quelle, Repository und Maintainer;
- exakte Modul-, Distribution- und Dependency-Versionen;
- vollständiger Commit-SHA und SHA-256-Integrität;
- Lizenz und gelockter Dependency-Satz;
- Manifest mit Capabilities, Permissions und Dependencies;
- Settings-Schema mit markierten Secrets und dokumentierten Endpoints;
- Datei-, Netzwerk-, Telemetrie- und Browserzugriffe;
- Persistence-Schema, Tabellen und sämtliche Migrationen;
- Jobs, Lifecycle-Hooks, API-Router und Frontend-Contributions;
- SBOM und Ergebnisse der Dependency-, Secret- und SAST-Scans;
- Disable-, Datenhaltungs- und Incident-Verhalten.

Die geprüfte Auflösung gehört in den Installer-/Deploymentzustand, nicht in ein vom
Paket selbst kontrolliertes Manifest und nicht in einen Runtime-Trust-Wrapper.

## Unterstützte Implementierungswege

- Konfiguration und Secrets: typisiertes `ModuleContext.settings`, keine selbst
  gelesene Prozessumgebung oder `.env`-Datei;
- Datenbank: `ModuleContext.database`, eigene Tabellen und Repositories;
- andere Module: öffentliche Service-/Event-Contracts, keine internen Imports;
- Netzwerk: Host-Port, deklarierte Hosts, Timeouts, Limits und sichere Redirects;
- Jobs: `ModuleContext.scheduler`, keine versteckten In-Process-Timer;
- Benutzerrechte: registrierte Permissions und serverseitige Prüfung;
- UI: deklarierte Contributions in den vorgesehenen Slots.

Diese Verträge ermöglichen Review und Wartbarkeit. Sie sind keine OS-, PostgreSQL-,
Python- oder Browser-Sandbox. Nicht ausreichend vertrauenswürdiger Code muss als
Remote Integration über eine stabile, eng begrenzte API angebunden werden.
