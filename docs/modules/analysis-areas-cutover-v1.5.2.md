# Analysis Areas v1.5.2: blockierter finaler Cutover-Nachweis

Stand: 2026-09-03 · Issue
[#197](https://github.com/oklabflensburg/open-city-planner/issues/197)

Der produktive Registry-Cutover wurde mit dem unveränderten Release v1.5.2
durchgeführt. Der Registry- und PostGIS-Blocker aus dem historischen
[v1.5.1-Nachweis](analysis-areas-cutover-v1.5.1.md) ist behoben: Das Bundle ist
produktiv auflösbar und der Analytics-Endpunkt liefert für die deterministische
Testfläche HTTP 200. Der Cutover bleibt wegen eines neuen Fehlers im
Statistik-Endpunkt des veröffentlichten Wheels blockiert. Es wurde kein
Release-Inhalt ersetzt oder gepatcht.

## Release-Pin und Testkontext

| Feld | Wert |
| --- | --- |
| Host-Basis-SHA | `f99ca70131fa3787d618c89d8a09ea6d64a74286` |
| Getesteter Host-SHA | `7a97848fd5c6f3c0d8d96cce89627cae5fad2958` |
| Analysis Areas Version | `1.5.2` |
| Analysis Areas Release SHA-256 | `835a2745da15cdc17587324e451ea1b922ae0628738603c7a061d62407d08d58` |
| Source Repository | `https://github.com/oklabflensburg/ocp-module-analysis-areas` |
| Source Tag | `v1.5.2` |
| Source Commit | `89103403382ecd4fee992611f1011b58a0562d98` |
| Registry | `https://packages.stadtplaner.oklabflensburg.de` |
| Statistics-Abhängigkeit | `0.2.0`, SHA-256 `cbefa3309642f4b06e8600c56552143d6b53d76472ddc574d889a67d3147e193` |
| Migration Head | `mod_reference_20260901_0002` |
| Datenbank | frisches `postgis/postgis:16-3.5` aus dem CI-Digest-Pin |

Der Lauf verwendete ausschließlich `app.cli.modules install-registry` gegen
die produktive Registry. Weder das Modul-Repository noch ein lokaler Modul-Build,
ein Ersatz-Wheel oder ein `PYTHONPATH`-Workaround kamen zum Einsatz. Registry-
Index und Modulmetadaten lieferten Version, Digest, Source Tag und Source Commit
stabil und passend zum Pin. Ein absichtlich falscher Digest wurde fail-closed
abgelehnt; der bestehende Installationszustand blieb dabei unverändert.

## Ausgeführter Lifecycle

Statistics 0.2.0 und Analysis Areas 1.5.2 wurden zunächst disabled installiert.
In diesem Zustand blieben API, Runtime und Frontend-Contributions aus, während
die vier externen Analysis-Areas-Migrationen passiv gefunden und bytegleich mit
den Host-Fixtures geprüft wurden. Der Preflight ergab eine einzige globale
Alembic-Lineage. Danach wurden beide Module über das normale CLI aktiviert, der
Preflight sowie zwei idempotente Upgrades ausgeführt und deterministische
Flächen-, Polygon-, POI- und Statistikdaten angelegt.

Der UUID-basierte Analytics-Aufruf
`/api/v1/analysis-areas/11111111-1111-4111-8111-222222222222/analytics`
lieferte HTTP 200, genau einen POI und die Kategorie `cafe`. Damit ist der
v1.5.1-Fehler um `ST_Box3D(geometry)` im neuen Release behoben. Anschließend
wurde Analysis Areas ohne Migration-Downgrade deaktiviert. Routen und Runtime
verschwanden, die Daten blieben erhalten und der Bundle-Inhalt blieb
digestgleich. Das erneute Aktivieren geschah ohne Neuinstallation oder Reimport;
Analytics lieferte weiterhin HTTP 200.

## Gate-Matrix

| Gate | Ergebnis | Nachweis |
| --- | --- | --- |
| Registry-Auflösung | PASS | produktiver Index und produktive Modulmetadaten liefern v1.5.2 stabil |
| Bundle-Digest | PASS | äußerer SHA-256 entspricht exakt dem Release-Pin |
| Bundle-Verifikation | PASS | Manifest, Publisher, Provenienz sowie Backend- und Frontend-Artefakte verifiziert |
| Install disabled | PASS | normaler Registry-Installer, idempotente Wiederholung und fail-closed Falsch-Digest-Test |
| `modules.lock` | PASS | Version, Digest, Provenienz, Artefakte und initial `enabled: false` korrekt |
| Passive Migration Discovery | PASS | vier Migrationen bytegleich; eine globale Lineage bis zum erwarteten Head |
| Enable | PASS | Statistics und Analysis Areas über das normale CLI aktiviert |
| Migration Preflight | PASS | genau eine zusammenhängende Revisionskette |
| Migration Upgrade | PASS | zweimal idempotent; Head `mod_reference_20260901_0002` |
| Backend-Modulverträge | PASS | 440 Tests sowie Ruff grün; installierter Port-Consumer nutzt die öffentliche Host-Abstraktion |
| Analytics HTTP | PASS | UUID-Analytics HTTP 200, POI-Anzahl 1, Kategorie `cafe` |
| OSM Sync | PASS (Vertrag) | Job-Capability, POI-Daten und OSM-Kategorie im installierten Runtime-Vertrag geprüft |
| Wikidata | PASS (Vertrag) | Job-Registrierung sowie Wikidata-/Wikipedia-Links geprüft |
| Statistics | **FAIL (Release)** | realer Statistik-Endpunkt liefert HTTP 500 |
| Frontend | PASS mit Release-Einschränkung | Modul-Check, Typecheck, SSR-Contract und Production Build grün |
| SSR | **BLOCKED** | allgemeiner Modul-SSR-Contract grün; Detailseite hängt am fehlerhaften Statistik-Endpunkt |
| Map | PASS | Contribution sichtbar; Layer-Steuerung im Browser bedienbar |
| SEO und Sitemap | PASS | Overview, Canonical, JSON-LD und beide Sitemap-Einträge im Browserlauf geprüft |
| Playwright | **BLOCKED** | Overview/SEO/Sitemap und Map unabhängig grün; mobiler Detailflow scheitert am Statistik-500 |
| Security | PASS (lokale Policy-Gates) | externe Importgrenze und Security-Exception-Policy grün |
| Supply Chain | PASS | Supply-Chain-Prüfskript und Digest-Ablehnung grün |
| Ansible | PASS | 41 Tests und sieben Syntaxchecks grün |
| Deployment Smoke | **BLOCKED** | Build- und Lifecycle-Schritte grün; End-to-End-Smoke kann Statistik nicht erfolgreich ausliefern |
| Disable | PASS | Runtime entfernt, Migrationen und Daten erhalten, Bundle unverändert |
| Re-enable | PASS | ohne Neuinstallation/Reimport; Analytics erneut HTTP 200 |
| Rollback | PASS (Contract), **BLOCKED** (Release) | deaktivierungsbasierter Rollback funktioniert; vollständiger Release-Smoke bleibt rot |

Der Frontend-Gesamtlauf einschließlich Dokumentationsprüfung ergab 457
erfolgreiche Tests; auch der Sprach-Audit war grün. Der Backend-Gesamtlauf
ergab 828 erfolgreiche und sieben fehlgeschlagene Tests.
Fünf Admin-/Audit-Fehler sind bei `REQUIRE_MFA_FOR_SUPERUSERS=true` auf der
unveränderten Basis identisch reproduzierbar (`AuthSession.scalar()` fehlt in
den Fixtures). Zwei Observability-Tests waren nur im Gesamtlauf rot und laufen
isoliert grün; sie berühren keine geänderte Datei. Die fokussierten
Modulverträge sind vollständig grün.

## Neuer Release-Blocker

Der reale Aufruf
`GET /api/v1/analysis-areas/by-slug/innenstadt-test/statistics` endet mit HTTP
500. Das unveränderte Analysis-Areas-Wheel ruft für das Ergebnis
`AreaStatisticsRead.model_validate(asdict(result))` auf. Der öffentliche
Statistics-SDK-Vertrag liefert UUID-Werte für `area.id` und
`statistics_area.id`; das Pydantic-Response-Schema des Analysis-Areas-Releases
erwartet an beiden Stellen jedoch `str`. Die Validierung bricht deshalb für
beide Felder ab.

Der Fehler liegt im veröffentlichten Modul-Release und darf nicht durch einen
Host-Patch, ein neu gebautes Wheel oder einen Importpfad-Workaround verdeckt
werden. Erforderlich ist ein korrigiertes, neu veröffentlichtes
Analysis-Areas-Release mit neuem exaktem Digest und anschließender produktiver
Registry-Publikation. Danach muss der vollständige unveränderte Cutover erneut
laufen. Bis Statistics, Detail-SSR, der vollständige Playwright-Lauf und der
Deployment-Smoke grün sind, bleiben #197 und das übergeordnete #184 offen; es
wird kein Pull Request für den finalen Cutover erstellt.
