# Deployment und Betrieb

Diese Anleitung bündelt den produktiven Betrieb des aktuellen Repositorys. Spezialisierte Abläufe bleiben in den verlinkten Dokumenten maßgeblich. Das Repository enthält systemd-Units für Hintergrundaufgaben, aber keine fertige Unit für den dauerhaften FastAPI- oder Nuxt-Hauptprozess und keine produktive Nginx-Konfiguration.

## Architektur

- Das Nuxt-Frontend wird als eigener Produktionsprozess betrieben.
- FastAPI stellt die API, `/health/live` und `/health/ready` bereit.
- PostgreSQL mit PostGIS ist die fachliche Datenbank.
- Redis dient als Cache und als gemeinsames Backend für produktive Sicherheitszähler. Er ist keine fachliche Datenquelle.
- Ein Reverse Proxy veröffentlicht Frontend und API über HTTPS.
- systemd-Timer starten OSM-Sync, Statistikimport, E-Mail-Outbox und optional Social Publishing.

## Voraussetzungen

- uv 0.12.5; Ansible installiert damit die verwaltete Python-Version 3.12.14;
- Node.js 22.23.2 als in der CI verwendete Version;
- pnpm 11.22.0 gemäß `frontend/package.json` und CI;
- PostgreSQL mit PostGIS; die CI prüft derzeit PostgreSQL 16 mit PostGIS 3.5;
- Redis für die empfohlene Produktionskonfiguration;
- für den OSM-Import zusätzlich die in [osm-hourly-sync.md](osm-hourly-sync.md) genannten Werkzeuge und Kapazitäten.

Andere produktive PostgreSQL-, PostGIS- oder Redis-Versionen sind im Repository nicht als feste Supportmatrix definiert und müssen vor dem Einsatz geprüft werden.

## Installationspfad und Service-Benutzer

Die meisten mitgelieferten Units und OSM-Skripte verwenden `/opt/git/open-city-planner` und den Benutzer `oklab` mit Gruppe `www-data`. Die Statistik-Unit verwendet dagegen `/opt/stadtplaner` und den Benutzer `stadtplaner`. Diese Abweichung ist kein zweites zwingendes Deploymentmodell: Wählen Sie einen Installationspfad und einen nicht privilegierten Service-Benutzer und gleichen Sie alle Units vor der Installation daran an.

Persistente Verzeichnisse wie Uploads, OSM-Daten und Social-Screenshots dürfen nicht bei jedem Deployment ersetzt werden. Der Service-Benutzer benötigt nur für die tatsächlich verwendeten Pfade Schreibrechte.

## Repository aktualisieren

Arbeiten Sie in einem vorab festgelegten Release- oder Branch-Verfahren. Ein typischer nicht interaktiver Aktualisierungsschritt im vorhandenen Checkout ist:

```bash
cd /opt/git/open-city-planner
git fetch --prune
git status --short
git pull --ff-only
```

Prüfen Sie vor `git pull`, dass der Produktionscheckout keine unbeabsichtigten lokalen Änderungen enthält. `.env`-Dateien, Uploads und Datenverzeichnisse dürfen nicht Teil des Git-Austauschs sein.

## Backend installieren und migrieren

```bash
cd /opt/git/open-city-planner/backend
python3 -m pip install 'uv==0.12.5'
uv python install 3.12.14
uv sync --frozen --no-dev --no-editable --python 3.12.14 --managed-python
uv run alembic heads
uv run alembic upgrade head
```

Die produktive Installation verwendet keine Development-Extras. CI und lokale
Vorabprüfungen ergänzen dagegen `--extra dev` für Pytest und Ruff. Beide Pfade
verwenden dasselbe `backend/uv.lock`; eine Auflösung auf dem Produktionsserver
findet nicht statt. Der unterstützte manuelle Produktionsweg bleibt das
Ansible-Playbook, das auch uv und Python exakt bereitstellt.

Vor einer Migration mit Schema- oder Datenänderungen ist ein Datenbankbackup erforderlich. Prüfen Sie die konkrete Migration und ihren erwarteten Laufzeitbedarf. Ein pauschales `alembic downgrade` ist kein sicherer Produktionsrollback. Legen Sie für riskante Änderungen einen gezielten Rollback- oder Vorwärtskorrekturplan fest.

## Frontend installieren und bauen

```bash
cd /opt/git/open-city-planner/frontend
pnpm install --frozen-lockfile
pnpm build
```

Der Produktionsprozess startet den von Nuxt erzeugten Server-Output nach dem für die jeweilige Plattform eingerichteten Verfahren. Das Repository liefert dafür keine allgemeingültige systemd-Unit aus.

## Environment

Kopieren Sie `.env.example` nicht ungeprüft als Produktionskonfiguration. Die Beispiele enthalten Entwicklungswerte und leere optionale Integrationen. Maßgeblich sind `backend/.env.example`, `frontend/.env.example` und `backend/app/core/config.py`.

Wichtige Backend-Gruppen:

- Basis: `APP_ENVIRONMENT`, `APP_BASE_URL`, `API_BASE_URL`, `DATABASE_URL`, `CORS_ORIGINS`, `LOG_LEVEL`;
- Authentifizierung: `JWT_SECRET_KEY`, `OAUTH_STATE_SECRET`, Cookie-, MFA- und WebAuthn-Variablen;
- E-Mail und Kontakt: `EMAIL_BACKEND`, `SMTP_*`, `CONTACT_*`, optional `TURNSTILE_*`;
- Cache und Limitierung: `REDIS_*`, `CACHE_PREFIX`, `AUTH_RATE_LIMIT_BACKEND`, `RATE_LIMIT_FAIL_CLOSED`;
- OSM und Geocoding: `OSM_*`, `OVERPASS_*`, `NOMINATIM_*`;
- Statistik: `FLENSBURG_SUPERSET_*`;
- Assistant: `AI_SEARCH_*`, `GROQ_*`;
- Integrationen: `MASTODON_*`, optionale OAuth-Provider und `MASTODON_SSO_*`;
- Dateien: `AVATAR_UPLOAD_DIR`, `MEDIA_BASE_URL`, `MASTODON_SCREENSHOT_DIRECTORY`.

Wichtige Frontend-Variablen beginnen mit `NUXT_PUBLIC_` und sind per Definition öffentlich. Secrets dürfen dort niemals gespeichert werden.

## Datenbank und Backups

PostgreSQL benötigt die PostGIS-Erweiterung. Trennen Sie nach Möglichkeit die Laufzeitrolle der Anwendung von Rollen für Migration und OSM-Import. Sichern Sie mindestens:

- die PostgreSQL-Datenbank einschließlich Alembic-Stand;
- Uploads unter dem konfigurierten `AVATAR_UPLOAD_DIR`;
- externe OSM-Arbeitsdaten, wenn deren Wiederaufbau nicht Teil des Recovery-Plans ist;
- serverseitige Environment- und Secret-Konfiguration über die vorgesehene Geheimnisverwaltung.

Backups müssen verschlüsselt, zugriffsgeschützt und durch Wiederherstellungstests überprüft werden. Tests und E2E dürfen niemals gegen die Produktionsdatenbank laufen.

## Redis

PostgreSQL/PostGIS bleibt Source of Truth. Für den Produktivbetrieb verlangt die Sicherheitscheckliste Redis für gemeinsame Limitierungszustände und empfiehlt einen eindeutigen `CACHE_PREFIX`. Redis darf nur über localhost oder ein privates Netz erreichbar sein und wird nicht durch den Reverse Proxy veröffentlicht.

Status- und Cachebefehle sind in [redis-cache.md](redis-cache.md) dokumentiert.

## Reverse Proxy, Nginx und TLS

Das Repository enthält keine fertige Nginx-Site. Der eingesetzte Proxy muss:

- Frontend und `/api/` an die richtigen lokalen Prozesse weiterleiten;
- HTTPS erzwingen und die Anwendungssicherheitsheader erhalten;
- SSE-Antworten des Notification Centers ohne ungeeignetes Response-Buffering weitergeben;
- Request-Größen passend zu den serverseitigen Limits begrenzen;
- Forwarded Headers nur von bekannten Proxys an das Backend liefern.

Setzen Sie `TRUSTED_PROXIES`, Origins, Cookie- und WebAuthn-Werte exakt passend zur öffentlichen HTTPS-Origin. Einzelheiten stehen in [security/production-checklist.md](security/production-checklist.md).

## OpenStreetMap und Analysegebiete

Initialimport, Replikationszustand, systemd-Timer, Monitoring und Recovery sind vollständig in [osm-hourly-sync.md](osm-hourly-sync.md) beschrieben. Kurzprüfung:

```bash
sudo systemctl status stadtplaner-osm-update.timer
sudo journalctl -u stadtplaner-osm-update.service -n 100 --no-pager
scripts/osm/status.sh
```

Nach dem lokalen OSM-Import aktualisiert das Postprocessing die anwendungsseitigen Tabellen und Cache-Versionen. Analysegebiete werden mit dem CLI-Modul `app.cli.sync_analysis_areas` synchronisiert; Details stehen in [osm-data.md](osm-data.md).

## Kommunale Statistik

Die Statistik setzt vorhandene Gemeinde- und Stadtteil-Analysegebiete voraus:

```bash
cd /opt/git/open-city-planner/backend
.venv/bin/python -m app.cli.import_flensburg_statistics --discover-only
.venv/bin/python -m app.cli.import_flensburg_statistics
```

Die mitgelieferte Timer-Unit prüft die Quelle wöchentlich. Vor Installation müssen ihr Pfad und Service-Benutzer an die gewählte Umgebung angepasst werden. Importvertrag, Fehlerverhalten und Datenmapping stehen in [flensburg-statistics.md](flensburg-statistics.md).

## Assistant und Groq

Die erweiterte Sprachinterpretation ist optional. Tatsächlich verwendete Variablen sind:

```env
AI_SEARCH_ENABLED=false
AI_SEARCH_PROVIDER=groq
AI_SEARCH_MODEL=
GROQ_API_KEY=
GROQ_BASE_URL=https://api.groq.com/openai/v1
GROQ_TIMEOUT_SECONDS=8
GROQ_MAX_RETRIES=1
GROQ_TEMPERATURE=0.1
ASSISTANT_QUERY_LOGGING=false
```

`GROQ_API_KEY` bleibt ausschließlich im Backend. Ohne Aktivierung, Modell oder Schlüssel bleiben die deterministischen Suchbefehle verfügbar; nur die erweiterte Sprachinterpretation entfällt. Prüfen Sie Provider-Limits und das verwendete Modell vor der Aktivierung. Feste Preise werden nicht im Repository dokumentiert.

## Mastodon und E-Mail-Outbox

Social Publishing ist optional und wird in [social-publishing.md](social-publishing.md) beschrieben. Die E-Mail-Outbox verarbeitet unter anderem retryfähige Willkommensmails. Die Polygon-Outbox verarbeitet Seiteneffekte nach Flächenmutationen (Adressanreicherung, Cache-Invalidierung, Benachrichtigungen) zuverlässig asynchron. Mitgelieferte Timer:

```bash
sudo systemctl enable --now stadtplaner-polygon-outbox.timer
sudo systemctl enable --now stadtplaner-social-publisher.timer
sudo systemctl enable --now stadtplaner-email-outbox.timer
systemctl list-timers 'stadtplaner-*'
```

Installieren Sie nur Integrationen, die konfiguriert und benötigt werden. Die `.service`-Dateien sind One-shot-Aufgaben und werden durch ihre Timer gestartet.

## Empfohlene Deployment-Reihenfolge

1. Wartungsfenster und Backup prüfen.
2. Code aktualisieren und Diff beziehungsweise Release kontrollieren.
3. Backend-Abhängigkeiten installieren.
4. Alembic-Head und Migrationen prüfen und ausführen.
5. Frontend-Abhängigkeiten installieren und Produktions-Build erzeugen.
6. Hauptprozesse nach der lokalen Servicekonfiguration neu starten.
7. benötigte Worker und Timer prüfen.
8. Healthcheck, öffentliche Seiten, Karte und read-only Suche testen.
9. Logs auf neue Fehler prüfen.

## Sichere Smoke Tests

```bash
curl --fail --silent https://<api-origin>/health/live
curl --fail --silent https://<api-origin>/health/ready
curl --fail --silent https://<frontend-origin>/
curl --fail --silent https://<frontend-origin>/dokumentation
```

`/health/live` prüft ausschließlich den Prozesszustand, `/health/ready` prüft PostgreSQL und alle gemäß Konfiguration erforderlichen Abhängigkeiten. Der Readiness-Endpunkt liefert nur strukturierte Zustände, keine Verbindungsdetails oder Secrets. Prüfen Sie anschließend im Browser Karte, Gebietsseite, Dokumentationssuche und ausschließlich lesende Suchanfragen wie „Alle Stadtteile anzeigen“ oder „Wie viele POIs gibt es in der Altstadt?“. Führen Sie keine mutierenden E2E-Tests gegen Produktion aus.

## Rollback

- Halten Sie das zuvor veröffentlichte Commit beziehungsweise Release und den vorherigen Frontend-Build reproduzierbar bereit.
- Bei einer reinen Codeänderung kann nach Prüfung auf den vorherigen Stand zurückgeschaltet werden.
- Bei Datenbankänderungen bestimmen Backup, konkrete Migration und Datenänderung den Rollback. Verwenden Sie keinen ungeprüften automatischen Downgrade.
- Bei einem fehlerhaften Datenimport bleiben nach den vorhandenen Importverträgen zuletzt erfolgreich gespeicherte Daten erhalten; prüfen Sie dennoch die spezialisierte Recovery-Anleitung.

## Logs und Fehlerdiagnose

```bash
sudo journalctl -u <api-service> -n 200 --no-pager
sudo journalctl -u <frontend-service> -n 200 --no-pager
sudo journalctl -u stadtplaner-email-outbox.service -n 100 --no-pager
sudo journalctl -u stadtplaner-polygon-outbox.service -n 100 --no-pager
sudo journalctl -u stadtplaner-social-publisher.service -n 100 --no-pager
sudo systemctl list-timers 'stadtplaner-*'
```

Typische Prüfungen:

- Backend startet nicht: Production-Settings, Datenbank und Redis anhand der Startmeldung prüfen.
- HTTP 502: lokalen Frontend-/API-Prozess und Proxyziel prüfen.
- Karte bleibt leer: API-Origin, Kartenstil, Browserkonsole und OSM-Datenstand prüfen.
- Statistik fehlt: letzten Importlauf und vorausgesetzte Analysegebiete prüfen.
- Assistant fällt zurück: `AI_SEARCH_ENABLED`, Modell, Backend-Key und bereinigte Provider-Warnings prüfen.
- E-Mail oder Mastodon bleibt liegen: Timer, Outboxstatus und letzte Worker-Logs prüfen.

## Observability anbinden

Ansible injiziert den exakt ausgecheckten Git-SHA als `STADTPLANER_RELEASE_SHA` in API, Frontend und One-shot-Jobs. Behalten Sie `LOG_FORMAT=json`, `METRICS_ENABLED=true` und `ASSISTANT_QUERY_LOGGING=false` in Produktion. OpenTelemetry ist für den produktiven Deploy verpflichtend:

```env
OTEL_ENABLED=true
OTEL_SERVICE_NAME=stadtplaner-api
OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4317
OTEL_EXPORTER_OTLP_PROTOCOL=grpc
OTEL_TRACES_SAMPLER=parentbased_traceidratio
OTEL_TRACES_SAMPLER_ARG=0.1
```

Der normale Ansible-Deploy verwaltet OpenTelemetry Collector Contrib 0.153.0
und Grafana Tempo 2.10.7 mit geprüften SHA-256-Summen. OTLP (`4317`), Collector-
Health (`13133`), die interne Tempo-Ingest-Strecke (`4319`) und Tempo (`3200`)
lauschen nur auf Loopback. Vor dem Umschalten des `current`-Symlinks müssen
Collector und Tempo erreichbar sein. Nach dem API-Start erzeugt Ansible einen
gesampelten `/health/ready`-Trace und pollt Tempo bis zum Nachweis des aktuellen
Release-SHA; ein Fehler nutzt das bestehende atomare Rollback.

Der Nginx-vHost erzeugt `X-Request-ID`, schreibt datensparsame JSON-Access-Logs und schützt `/metrics` mit `allow`/`deny`. Tragen Sie das Netz des Monitoring-Hosts in `stadtplaner_metrics_allowed_cidrs` ein; veröffentlichen Sie keine Basic-Auth-Credentials in Templates. Der Prometheus-Scraper verwendet HTTPS und benötigt eine erlaubte Quelladresse.

```yaml
stadtplaner_metrics_allowed_cidrs:
  - 10.20.0.15/32
```

Die Beispielkonfiguration liegt unter `deploy/observability/prometheus/`. Importieren Sie anschließend `deploy/observability/grafana/stadtplaner-overview.json`. Für timerbasierte Jobs konfigurieren Sie node_exporter mit `--collector.textfile.directory=/data/stadtplaner/observability`; die atomisch aktualisierten `.prom`-Dateien enthalten keine Empfänger oder Payloads.

Alternativ installiert und provisioniert das separate, ausdrücklich opt-in
auszuführende Ansible-Playbook `playbooks/monitoring.yml` den vollständigen
lokalen Stack. Es ist nicht Bestandteil eines normalen Applikationsdeployments.
Die Anleitung einschließlich SSH-Tunnel, optionaler Grafana-Subdomain,
Retention, Backups und Fehlerdiagnose steht unter
[Prometheus und Grafana mit Ansible betreiben](monitoring-deployment.md).

Nach einem Deployment prüfen Sie:

```bash
curl -i https://<api-origin>/health/info
curl -i -H 'X-Request-ID: deploy-smoke' https://<api-origin>/health/live
curl --fail http://127.0.0.1:<backend-port>/metrics | grep build_info
journalctl -u stadtplaner-api -o cat | jq 'select(.request_id == "deploy-smoke")'
```

Prometheus-, Grafana-, Tempo- und Collector-Ausfälle nach einer erfolgreichen
Aktivierung dürfen weder Readiness noch Requests beeinflussen. Neue Deployments
bleiben dagegen bewusst fail-closed. Architektur, Datenschutz, SLOs, Alerts und
Runbooks sind in [observability.md](observability.md) beschrieben.

## Sicherheitscheckliste

- [ ] Keine Produktions-Secrets oder `.env`-Dateien sind im Repository.
- [ ] `DATABASE_URL`, `GROQ_API_KEY`, SMTP-, OAuth- und Mastodon-Secrets bleiben serverseitig.
- [ ] PostgreSQL und Redis sind nicht öffentlich erreichbar.
- [ ] Cookies, Origins, WebAuthn und Proxyvertrauen stimmen mit HTTPS überein.
- [ ] Ein aktuelles Datenbankbackup und ein geprüfter Recovery-Plan sind vorhanden.
- [ ] Migrationen wurden vor Ausführung geprüft.
- [ ] API-, Frontend- und Worker-Prozesse laufen ohne Root-Rechte.
- [ ] Logs, Uploads, Screenshots und Backups besitzen begrenzte Dateirechte.
- [ ] Keine E2E-Suite verwendet Produktionsdaten oder Produktionskonten.

## Deployment-Checkliste

- [ ] Code aktualisiert
- [ ] Abhängigkeiten installiert
- [ ] Datenbankbackup vorhanden
- [ ] Migrationen erfolgreich
- [ ] Frontend gebaut
- [ ] Hauptdienste neu gestartet
- [ ] benötigte Worker und Timer aktiv
- [ ] Healthcheck grün
- [ ] Suche und Karte geprüft
- [ ] Logs geprüft

Test- und CI-Details stehen in [ci.md](ci.md). Die ausführliche Produktionshärtung steht in [security/production-checklist.md](security/production-checklist.md).
