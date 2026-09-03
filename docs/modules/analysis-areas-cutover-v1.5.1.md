# Analysis Areas v1.5.1: finaler Cutover-Nachweis

Stand: 2026-09-03 · Issue
[#197](https://github.com/oklabflensburg/open-city-planner/issues/197)

Dieser Bericht trennt implementierte Gates von tatsächlich ausgeführten
Nachweisen. Ein blockiertes Gate wird nicht als erfolgreich gewertet.

## Release-Pin

| Feld | Wert |
| --- | --- |
| Host-Basis-SHA | `f99ca70131fa3787d618c89d8a09ea6d64a74286` |
| Analysis Areas Version | `1.5.1` |
| Analysis Areas Release SHA-256 | `8fd4b21c2da820f2d036f126848293395d4da772201f8473c07c0ef38e068bc9` |
| Source Repository | `https://github.com/oklabflensburg/ocp-module-analysis-areas` |
| Source Tag | `v1.5.1` |
| Source Commit | `e190c4c5a70df6dbbe1f538f82e68d30260fe071` |
| Registry | `https://packages.stadtplaner.oklabflensburg.de` |
| Migration Head | `mod_reference_20260901_0002` |

Das GitHub-Release-Asset `analysis-areas-1.5.1.ocp` wurde mit dem Host-CLI
verifiziert. Es ist ein Bundle v1 mit Backend-Wheel und Frontend-TGZ; ID,
Version, Publisher, Source Repository, Tag, Commit und Digest entsprechen dem
Pin oben. Der installierte Backend-Inhalt besitzt ausschließlich öffentliche
`app.platform.modules.sdk`-Imports. Die vier übernommenen Revisionen enden bei
`20260819_0032` und bleiben Teil der einen globalen Lineage.

Zusätzlich wurde das echte Release hermetisch über eine kontrollierte
Registry-v1-Testantwort installiert. Dieser Test nutzt unverändert
`ModuleRegistryClient`, Registry-Auflösung und -Download, Bundle-Validierung und
`ModuleInstaller`; nur die noch fehlenden öffentlichen Registry-Dokumente werden
lokal bereitgestellt. Dieser Nachweis ersetzt den produktiven Registry-Lauf
nicht.

## Implementierter Gate-Pfad

Der Job `analysis-areas-cutover` in `.github/workflows/module-contract.yml`
verwendet keinen Checkout und keinen lokalen Build des Modul-Repositories. Er
installiert `statistics@0.2.0` und anschließend `analysis-areas@1.5.1` mit
exakten Registry-Digests über `app.cli.modules install-registry`. Dieser Befehl
führt Registry-Auflösung, begrenzten HTTPS-Download, Digestprüfung, Bundle-
Verifikation und den normalen atomaren `ModuleInstaller` aus.

Das Gate prüft danach:

- `modules.lock` mit Version, äußerem Bundle-Digest, Publisher, Provenienz und
  `enabled: false` sowie eine idempotente zweite Installation;
- keinen Runtime-Pfad, keine API und keine Frontend-Contribution im disabled
  Zustand, aber passive, bytegleiche Migration Discovery;
- Enable-Preflight, zweimaliges idempotentes Alembic-Upgrade und den globalen
  Migration-Head;
- API-Liste, Detail, GeoJSON, Sitemap, Analytics, Comparison, Polygone,
  Wikidata-/Wikipedia-Links, registrierten Wikidata-Job und Modul-Capabilities;
- Frontend-Preflight, Typecheck, SSR-Contract und Production Build;
- Playwright für `/gebiete`, `/gebiete/:slug`, Navigation, Map-Layer und
  Layer-Interaktion, POI-Navigation, Statistikdarstellung, externe Links,
  responsive Darstellung, Canonical/JSON-LD und Sitemap;
- Disable ohne Downgrade oder Datenverlust, Build des Hosts ohne
  Analysis-Areas-Runtime und anschließendes Re-enable ohne Neuinstallation oder
  Datenimport.

Der Ansible-Beispielpin verwendet ebenfalls v1.5.1 und den exakten Digest. Die
Rolle installiert weiterhin vor Environment-Rendering, Migration-Preflight,
Upgrade, Frontend-Build und Start-Smoke. Aktivierung bleibt eine separate,
bewusste `modules.lock`-Änderung.

## Ausgeführte Nachweise

| Gate | Ergebnis | Nachweis |
| --- | --- | --- |
| Release-Asset und `.ocp verify` | PASS | echtes GitHub-Asset, SHA-256 und Host-CLI |
| Registry-Schema/Resolve 1.5.1 | BLOCKED | produktive Registry führt am 2026-09-03 nur `analysis-areas@1.0.0` |
| Install disabled | PASS (hermetisch), BLOCKED (Registry) | echter Release-Download wird normal validiert und disabled installiert; produktiver Resolver lehnt die nicht registrierte Version fail-closed ab |
| Passive Migration Discovery | PASS (echtes Release, hermetisch) | alle vier Migrationen bytegleich, Preflight zeigt eine globale Lineage bis `mod_reference_20260901_0002` |
| Enable | PASS (hermetisch), BLOCKED (Registry) | normale Aktivierung von Statistics und Analysis Areas erfolgreich; produktiver Registry-Pfad nicht erreichbar |
| Backend | PASS mit Einschränkung | Ruff und 86 relevante Modul-/Installer-/Registry-Tests grün; Gesamtsuite hat sechs bestehende Admin-/Audit-Fixture-Fehler |
| Runtime/API | BLOCKED (Release) | Registrierung, Routen, Liste, GeoJSON, Sitemap und Detail funktionieren; Analytics endet wegen `ST_Box3D(geometry)` mit HTTP 500 |
| Frontend | PASS (Slim Host), BLOCKED (Release) | 457 Tests, Typecheck, Production Build und Sprach-Audit grün; aktivierter Modullauf stoppt am Backend-Releasefehler |
| SSR | BLOCKED | implementiert; vollständiger aktivierter Lauf erreicht das SSR-Gate wegen des API-Fehlers nicht |
| Map | BLOCKED | Playwright-Gate implementiert; vollständiger Lauf erreicht es wegen des API-Fehlers nicht |
| OSM Sync | BLOCKED | Runtime-Registrierung im Gate geprüft; vollständiger Lauf endet zuvor am API-Fehler |
| Wikidata | PASS teilweise, BLOCKED gesamt | Capability, Job-Registrierung und Detail-Links funktionieren; vollständiger Lauf endet am API-Fehler |
| E2E | BLOCKED | drei Playwright-Flows sind implementiert, werden aber erst nach bestandenem Backend-Smoke gestartet |
| Security | PASS (lokal) | Architecture-/Import-Gates und Security-Unit-Gates grün |
| Supply Chain | PASS (lokal) | `scripts/verify-supply-chain.py` grün; Registry-Digest bleibt fail-closed |
| Deployment | PASS mit Einschränkung | 41 Ansible-Tests und sieben Syntaxchecks grün; production-like Modul-Smoke blockiert |
| Disable | BLOCKED | Lifecycle stoppt fail-closed vor diesem Schritt |
| Re-enable | BLOCKED | Lifecycle stoppt fail-closed vor diesem Schritt |
| Rollback | PASS (Contract), BLOCKED (Release) | kein Downgrade im Runbook/Gate; realer Lifecycle ist nicht vollständig erfolgreich |

## Blocker und Abschlussbedingung

Die produktive Registry liefert derzeit im Index und in
`/modules/analysis-areas.json` ausschließlich Version `1.0.0` mit SHA-256
`7006f31ea73f40e38f63d2065652c27ad5d3391ddcc8cfad2f149993efef3dcf`.
Der normale Installer beendet deshalb den exakten Aufruf für v1.5.1 mit
`Version "1.5.1" is not available for module "analysis-areas".`

Der hermetische Lauf zeigt außerdem einen Releasefehler, der nach einer
Registry-Publikation weiterhin blockieren würde: Der Analytics-Code im
veröffentlichten Wheel ruft `ST_Box3D(geometry)` auf. Diese Funktion existiert im
gepinnten PostGIS-16/3.5-Image nicht; PostGIS stellt dafür `Box3D(geometry)`
bereit. `/api/v1/analysis-areas/by-slug/innenstadt-test/analytics` antwortet
daher mit HTTP 500. Der Fehler ließ sich auch in einer frischen Instanz des
gepinnten Images unabhängig reproduzieren. Der Host ersetzt oder patcht das
veröffentlichte Wheel nicht.

Erforderlich sind daher ein korrigiertes, neu veröffentlichtes Modul-Release und
dessen separate, reviewte Registry-Publikation mit neuem exakten Digest. Danach
müssen Pin und Gate auf dieses Release aktualisiert und der unveränderte
Registry-Cutover-Lifecycle vollständig erfolgreich ausgeführt werden. Erst dann
dürfen die BLOCKED-Zeilen auf PASS gesetzt und #197 beziehungsweise #184
geschlossen werden.

Bekannte nicht-blockierende Einschränkung: Der lokale Backend-Gesamtlauf endet
außerhalb dieses Changes in sechs Admin-/Audit-Tests, weil deren `AuthSession`-
Fixture die inzwischen abgefragte Methode `scalar()` nicht bereitstellt. Die
fokussierten 86 Modul-/Installer-/Registry-Tests und das lokale
`scripts/module-contract-gate` sind grün.
