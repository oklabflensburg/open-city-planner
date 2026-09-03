# Analysis Areas v1.5.3: blockierter finaler Cutover-Nachweis

Stand: 2026-09-03 · Issue
[#197](https://github.com/oklabflensburg/open-city-planner/issues/197)

Der produktive Registry-Cutover wurde mit dem unveränderten Release v1.5.3
durchgeführt. Der Statistics-Fehler aus v1.5.2 ist behoben: Analytics,
Statistics Summary und Statistics Series liefern mit dem installierten Release
HTTP 200. Der finale Cutover bleibt wegen einer nicht wirksamen
POI-Kartenfilter-Navigation im veröffentlichten Frontend-Artefakt blockiert. Es
wurde kein Release-Inhalt ersetzt oder gepatcht.

## Release-Pin und Testkontext

| Feld | Wert |
| --- | --- |
| Host-Basis-SHA | `f99ca70131fa3787d618c89d8a09ea6d64a74286` |
| Getesteter Host-SHA | `9d46e365fcbc21cf23bbea82502a98374b4b5caa` (Cutover-Code; dieser Nachweis folgt als separater Dokumentations-Commit) |
| Analysis Areas Version | `1.5.3` |
| Analysis Areas Release SHA-256 | `88ead403d89209c155b78101676b691a642139991cf9fd0787115ccfe0338f6b` |
| Source Repository | `https://github.com/oklabflensburg/ocp-module-analysis-areas` |
| Source Tag | `v1.5.3` |
| Source Commit | `06a675a4237fca397b37c0aeb935ecd60557073a` |
| Registry | `https://packages.stadtplaner.oklabflensburg.de` |
| Registry Channel | `stable` |
| Statistics-Abhängigkeit | `0.2.0`, SHA-256 `cbefa3309642f4b06e8600c56552143d6b53d76472ddc574d889a67d3147e193` |
| Migration Head | `mod_reference_20260901_0002` |
| Datenbank | frisches `postgis/postgis:16-3.5` aus dem CI-Digest-Pin |

Der Lauf verwendete ausschließlich `app.cli.modules install-registry` gegen
die produktive Registry. Weder das Modul-Repository noch ein lokaler Modul-Build,
ein Ersatz-Wheel, eine direkte Wheel-Installation oder ein `PYTHONPATH`-Workaround
kamen zum Einsatz. Registry-Index und Modulmetadaten lieferten Version, Digest,
Source Tag und Source Commit passend zum Pin.

## Ausgeführter Lifecycle und Regressionen

Statistics 0.2.0 und Analysis Areas 1.5.3 wurden disabled installiert. In
diesem Zustand fehlten API-, Job-, Runtime-, Navigations-, Map- und
Sitemap-Contributions, während die vier externen Analysis-Areas-Migrationen
passiv gefunden und bytegleich mit den Host-Fixtures geprüft wurden. Der
Disabled-Frontend-Build war erfolgreich.

Danach wurden beide Module über das normale CLI aktiviert. Der modulbewusste
Preflight und zwei idempotente Upgrades liefen auf einer frischen PostGIS-
Datenbank bis zum gemeinsamen Head `mod_reference_20260901_0002`. Die
deterministischen Seeds enthielten danach zwei Analysegebiete und zwei
Statistikbeobachtungen.

Der produktive UUID-Pfad
`/api/v1/analysis-areas/11111111-1111-4111-8111-222222222222/analytics`
lieferte HTTP 200, eine gültige Bounding Box, genau einen POI und die Kategorie
`cafe`; der historische `ST_Box3D`-Fehler trat nicht auf. Sowohl
`/api/v1/analysis-areas/by-slug/innenstadt-test/statistics` als auch
`/api/v1/analysis-areas/by-slug/innenstadt-test/statistics/cutover_population`
lieferten HTTP 200. `area.id` und `statistics_area.id` waren in beiden JSON-
Antworten Strings; Series-Datum und Dezimalwert waren korrekt serialisiert.

## Gate-Matrix

| Gate | Ergebnis | Nachweis |
| --- | --- | --- |
| Registry resolution | PASS | produktiver Stable-Channel löst `analysis-areas@1.5.3` auf |
| Digest | PASS | Registry- und heruntergeladener Bundle-Digest entsprechen exakt dem Pin |
| Bundle verify | PASS | Manifest, Publisher, Provenienz sowie Backend- und Frontend-Artefakte verifiziert |
| Install disabled | PASS | normaler produktiver Registry-/Installerpfad, keine implizite Aktivierung |
| `modules.lock` | PASS | Version 1.5.3, exakter Digest, Provenienz und `enabled: false` korrekt |
| Passive migration discovery | PASS | vier historische Migrationen bytegleich und disabled discoverbar |
| Enable | PASS | Statistics und Analysis Areas über das normale CLI aktiviert |
| Migration preflight | PASS | eine zusammenhängende globale Lineage |
| Migration upgrade | PASS | zweimal idempotent bis `mod_reference_20260901_0002` |
| Backend | PASS für #197 | installierte Runtime, API-Characterization und Port-Consumer grün |
| Analytics HTTP | PASS | HTTP 200, POI-Analytics und Bounding Box gültig |
| Statistics Summary HTTP | PASS | HTTP 200, beide IDs als JSON-Strings, Daten vorhanden |
| Statistics Series HTTP | PASS | HTTP 200, beide IDs als JSON-Strings, Datum/Decimal und Series vorhanden |
| OSM Sync | PASS (Vertrag) | OSM-Daten und öffentlicher Port-Consumer im installierten Runtime-Vertrag geprüft |
| Wikidata | PASS (Vertrag) | Job-Capability sowie Wikidata-/Wikipedia-Links geprüft |
| Frontend | PASS | Modul-Preflight, Typecheck, SSR-Contract und aktiver Production Build grün |
| SSR | PASS | Modul-SSR-Contract und reale Gebietsdetailseite grün |
| Map | PASS | Layer-Contribution sichtbar und im Browser bedienbar |
| SEO | PASS | Overview, Canonical und JSON-LD im Browserlauf geprüft |
| Sitemap | PASS | `/gebiete` und `/gebiete/innenstadt-test` enthalten |
| Playwright | **FAIL (Release)** | 2 von 3 Flows PASS; POI-Link setzt keinen wirksamen Kartenfilter |
| Security | PASS (lokale Policy-Gates) | externe Importgrenze und Security-Policy-Tests grün |
| Supply Chain | PASS | lokale Supply-Chain-Prüfungen und exakter Release-Pin grün |
| Ansible | PASS | Unit- und Syntaxprüfungen grün |
| Deployment smoke | **BLOCKED** | Build/Start/API grün; vollständiger Nutzerflow ist wegen POI-Navigation rot |
| Disable | **NOT RUN** | laut Ablauf erst nach vollständig grünem aktivem Zustand |
| Re-enable | **NOT RUN** | wegen blockiertem Disable-Schritt nicht begonnen |
| Rollback | PASS (Runbook), **BLOCKED** (Release) | deaktivierungsbasierter Ablauf dokumentiert; v1.5.3-Abschluss nicht freigegeben |

Die vollständige Backend-Suite auf einer korrekt initialisierten frischen
PostGIS-Datenbank ergab 828 PASS und sieben FAIL. Fünf Admin-/Audit-Fehler bei
`REQUIRE_MFA_FOR_SUPERUSERS=true` sind auf der unveränderten Base identisch
reproduzierbar, weil deren `AuthSession`-Fixtures keine `scalar()`-Methode
bereitstellen. Zwei Observability-Tests sind auf Cutover und Base nur im
Gesamtlauf rot und laufen isoliert grün. Diese sieben Baselinefehler sind
unabhängig vom Cutover. Der Frontend-Gesamtlauf ergab 457 PASS; Typecheck,
Disabled-/Enabled-Build, SSR-Contract, Sprach- und SEO-Audit waren grün.

## Historische Releaseblocker

- v1.5.1 verwendete in PostGIS Analytics ungültig `ST_Box3D(...)`. Der Fehler
  ist seit v1.5.2 behoben; v1.5.1 blieb unverändert.
- v1.5.2 übergab UUID-Objekte des Statistics-SDK direkt an String-Felder seines
  API-Vertrags. Der Fehler ist in v1.5.3 behoben; v1.5.2 blieb unverändert.

## Neuer Releaseblocker

Der mobile reale Nutzerflow klickt auf den Link für die POI-Kategorie `cafe`.
Das installierte Frontend-Artefakt erzeugt
`/karte?gebiet=innenstadt-test&poi=cafe`. Die Analysis-Areas-Map-Contribution
wertet `gebiet` beziehungsweise `area` aus, verarbeitet `poi` aber nicht. Der
fachneutrale Slim Host besitzt nach dem abgeschlossenen Host-Cleanup bewusst
keine Analysis-Areas-spezifische Query- oder Filterlogik. Die Kategorie wird
daher nicht als OSM-Kartenfilter angewandt; der bestehende Playwright-Vertrag
erwartet weiterhin die wirksame POI-Navigation und schlägt fehl.

Der Fehler liegt im veröffentlichten Modul-Release. Er darf nicht durch eine
abgeschwächte Assertion, Host-Sonderlogik oder ein lokal verändertes Bundle
verdeckt werden. Erforderlich ist ein korrigiertes, neu veröffentlichtes
Analysis-Areas-Release mit immutablem Digest, das die POI-Auswahl über einen
vorhandenen fachneutralen Kartenvertrag wirksam macht. Danach muss der
vollständige Registry-Cutover erneut laufen. Bis alle Playwright-Flows sowie
Disable und Re-enable grün sind, bleiben #197 und #184 offen; es wird kein Pull
Request für den finalen Cutover erstellt.
