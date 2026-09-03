# Analysis Areas v1.5.3: finaler Cutover-Nachweis

Stand: 2026-09-03 · Issue
[#197](https://github.com/oklabflensburg/open-city-planner/issues/197) · **PASS**

Der finale produktionsnahe Registry-Cutover wurde mit dem unveränderten Release
v1.5.3 vollständig bestanden. Der kanonische Host-Vertrag aus #216 / PR #217
verwendet `poi` durchgängig; Analytics, Statistics Summary, Statistics Series,
der reale POI-Kartenflow sowie Disable und Re-enable sind grün. Es wurde weder
ein Modul-Artefakt verändert noch ein neues Modul-Release erzeugt oder
ausgerollt.

## Release-Pin und Testkontext

| Feld | Wert |
| --- | --- |
| Kanonische Host-Basis | `3f6fe2ffd132ed011b0dac01d814c8e55cbb7414` (`staging/epic-91-modular-host`) |
| Getesteter Cutover-Code | `e6e987f3a758e30e1d04d70282a69d44b248eefa` (dieser Nachweis folgt als separater Dokumentations-Commit) |
| Analysis Areas Version | `1.5.3` |
| Analysis Areas SHA-256 | `88ead403d89209c155b78101676b691a642139991cf9fd0787115ccfe0338f6b` |
| Source Repository | `https://github.com/oklabflensburg/ocp-module-analysis-areas` |
| Source Tag | `v1.5.3` |
| Source Commit | `06a675a4237fca397b37c0aeb935ecd60557073a` |
| Registry / Channel | `https://packages.stadtplaner.oklabflensburg.de` / `stable` |
| Statistics-Abhängigkeit | `0.2.0`, SHA-256 `cbefa3309642f4b06e8600c56552143d6b53d76472ddc574d889a67d3147e193` |
| Migration Head | `mod_reference_20260901_0002` |
| Datenbank | frisches `postgis/postgis:16-3.5` mit dem in CI gepinnten Image-Digest |

Registry-Index und Modulmetadaten wurden live gegen die produktive Registry
aufgelöst. Installation und Lifecycle verwendeten ausschließlich den normalen
Pfad `app.cli.modules install-registry`. Es gab keinen lokalen Modul-Checkout,
keinen lokalen Modul-Build, kein Ersatz-Wheel, keine direkte Wheel-Injektion,
keinen `PYTHONPATH`- oder Host-/Modul-Workaround und keinen parallelen alten
Query-Vertrag. Registry, Tags, Releases und Produktionssysteme wurden nicht
verändert.

## Vollständiger Lifecycle

Statistics 0.2.0 und Analysis Areas 1.5.3 wurden zunächst disabled in einen
leeren Modul-Root installiert. Ein absichtlich falscher Digest wurde abgelehnt,
ohne das Lockfile zu verändern; die erneute Installation des korrekten Pins war
idempotent. Im Disabled-Zustand gab es keine Runtime-, API-, Job-, Navigations-,
Map- oder Sitemap-Contributions. Die externen Migrationen blieben passiv
auffindbar und waren bytegleich mit den Host-Fixtures. Modulprüfung und
Production Build waren disabled erfolgreich.

Anschließend wurden Statistics und Analysis Areas über das normale CLI
aktiviert. Preflight und zwei aufeinanderfolgende Upgrades waren idempotent und
endeten bei `mod_reference_20260901_0002`. Die deterministischen Host- und
Cutover-Seeds erzeugten zwei Analysegebiete und zwei Statistikbeobachtungen.
Es wurden keine Migrationen gestempelt, neu gebaselined oder heruntergestuft und
die Datenbank wurde während des Lifecycle nicht zurückgesetzt.

Der UUID-Analytics-Endpunkt lieferte HTTP 200, die erwartete Bounding Box und
genau einen POI mit `primary_type=cafe`. Statistics Summary und Series lieferten
HTTP 200; IDs wurden als Strings sowie Datum und Dezimalwert vertragsgemäß
serialisiert. Der Browserflow öffnete
`/karte?gebiet=innenstadt-test&poi=cafe`, beobachtete den realen Request
`/api/v1/osm/features?...&poi=cafe`, erhielt ausschließlich Cafe-Features und
prüfte dieselben Daten in der MapLibre-Quelle `osm-pois`. Der ausgemusterte
öffentliche Query-Key ist weder im URL-Vertrag noch im Request erforderlich.

Nach dem aktiven Gesamtlauf wurde Analysis Areas normal deaktiviert. Statistics
blieb aktiv, passive Migration Discovery, Disabled-Assertions, Modulprüfung und
Build blieben grün; Daten und Migrationsstand wurden nicht zurückgesetzt. Die
anschließende Reaktivierung erfolgte ohne Neuinstallation oder Reimport. Danach
bestanden Runtime-, API-, Analytics-, Statistics-, Frontend- und Browser-Smoke-
Prüfungen erneut.

## Gate-Matrix

| Gate | Ergebnis | Nachweis |
| --- | --- | --- |
| Registry-Auflösung / Metadaten | PASS | Stable löst beide exakten Versionen, Digests und die v1.5.3-Provenienz auf |
| Digest / Bundle-Verifikation | PASS | absichtlich falscher Digest abgelehnt; Manifest, Publisher, Provenienz und Artefakte des korrekten Bundles verifiziert |
| Install disabled / Lockfile | PASS | normaler Registry-Installer, `enabled: false`, zweite Installation idempotent |
| Passive Migration Discovery | PASS | externe Migrationen disabled auffindbar und bytegleich mit den Host-Fixtures |
| Enable / Migration | PASS | normales CLI, Preflight und zwei idempotente Upgrades bis zum exakten Head |
| Analytics HTTP | PASS | HTTP 200, Bounding Box und genau ein Cafe-POI |
| Statistics Summary HTTP | PASS | HTTP 200, String-IDs und erwartete Daten |
| Statistics Series HTTP | PASS | HTTP 200, String-IDs sowie korrektes Datum/Decimal |
| POI-Vertrag und reale Map-Daten | PASS | `poi=cafe` in URL, echtem Backend-Request, Response und MapLibre-Quelle; kein alter öffentlicher Query-Vertrag |
| Deep-Link / Reload / Änderung / Entfernen / History | PASS | isolierter #217-POI-E2E gegen frische PostGIS-Datenbank: 1/1 |
| Cutover Playwright | PASS | 3/3 reale Registry-Cutover-Flows |
| Standard Playwright | PASS | 55/55 auf frischer PostGIS-Datenbank, einschließlich #217-Regression |
| Backend Contracts | PASS | Architektur-Gate sowie 432 Tests; 8 erwartete DB-Skips im DB-losen Contract-Workflow |
| Backend Gesamt | PASS für den Cutover | 835/837 im Gesamtlauf; beide übrigen Tests exakt auf unveränderter Base reproduziert und isoliert grün |
| Frontend Unit | PASS | 80 Dateien, 462 Tests |
| Frontend Typecheck / Build | PASS | TypeScript, disabled/enabled Production Builds und finaler Build grün |
| Frontend Modul-Contracts / SSR | PASS | 7 Dateien, 59 Tests; SSR-Modulvertrag 3/3 |
| Map / SEO / Sitemap / Sprache | PASS | reale Karte, SEO-Audit, Sitemap-Verträge und 487 Ressourcen ohne unerlaubten Sprachfund |
| Security | PASS | Importgrenze, 6 Policy-Tests, Backend-/Frontend-Audits, negative Vulnerability-Fixture sowie Gitleaks-Historie/SARIF/Fixtures |
| Supply Chain | PASS | Policy-Verifikation, 8 Unit-Tests und Online-Prüfung sämtlicher Action-Pins |
| Ansible | PASS | 41 Unit-Tests und 7 Syntaxprüfungen |
| Deployment Smoke | PASS | Build, Start, APIs, Overview und reale Browserflows im lokalen produktionsnahen Stack |
| Disable | PASS | normale Deaktivierung ohne Downgrade oder Datenreset; disabled Verträge und Build grün |
| Re-enable | PASS | ohne Reinstall/Reimport; aktive Verträge, Analytics, Statistics und Overview erneut grün |
| Rollback | PASS | deaktivierungsbasierter Ablauf praktisch geprüft und unten dokumentiert |

### Einordnung der Backend-Gesamtsuite

Auf dem Cutover-Branch ergab der korrekt initialisierte Gesamtlauf 835 PASS und
zwei FAIL. Ausschließlich die beiden reihenfolgeabhängigen Observability-Tests
`test_request_id_response_log_metrics_and_route_cardinality` und
`test_fastapi_trace_contains_child_span_and_trace_id_in_log` waren betroffen;
beide bestanden jeweils isoliert in einem eigenen Prozess.

Gemäß der Baseline-Regel wurde derselbe vollständige Lauf in einem separaten
Worktree auf der unveränderten kanonischen Base
`3f6fe2ffd132ed011b0dac01d814c8e55cbb7414` und einer eigenen frischen,
vollständig initialisierten PostGIS-Datenbank wiederholt. Das Resultat war
identisch: 835 PASS, dieselben zwei FAIL; isoliert bestanden beide Tests auch
dort. Damit handelt es sich um exakt reproduzierte, bestehende
Reihenfolgeausreißer der Base und nicht um eine Cutover-Regression. Assertions,
Fixtures und Gates wurden nicht abgeschwächt.

## Historische Blocker und Auflösung

- v1.5.1 verwendete in PostGIS Analytics ungültig `ST_Box3D(...)`; der Fehler
  wurde behoben.
- v1.5.2 übergab UUID-Objekte des Statistics-SDK an String-Felder; der Fehler
  wurde in v1.5.3 behoben.
- Der erste v1.5.3-Cutover zeigte den Host-Query-Mismatch `poi` gegenüber dem
  früheren Key. #216 / PR #217 korrigierte den kanonischen, fachneutralen
  Host-Vertrag. Weil dies eine Host-Contract-Änderung war, blieb das immutable
  Analysis-Areas-Release v1.5.3 unverändert; ein neues Modul-Release war nicht
  erforderlich.

Die historischen Fehlläufe bleiben damit als Ursachen- und Release-Evidenz
erhalten, blockieren den finalen Lauf aber nicht mehr.

## Rollout und Rollback

Dieser Nachweis hat **kein Production Deploy** ausgeführt. Für den späteren
Rollout gelten weiterhin der exakte Host-Commit, die beiden Registry-Pins und
der normale modulbewusste Preflight-/Upgrade-Pfad. Nach dem Rollout müssen die
Analytics-, Statistics- und POI-Smokes erneut ausgeführt werden.

Der praktisch geprüfte Rollback deaktiviert Analysis Areas über das normale
Modul-CLI. Er verändert weder das Registry-Artefakt noch migriert er die
Datenbank zurück oder löscht Moduldaten; passive Migration Discovery bleibt
verfügbar und Statistics kann aktiv bleiben. Re-enable ohne Reinstall oder
Reimport stellt den Dienst wieder her. Die allgemeinen atomaren Host-Release-
und Symlink-Rollback-Schritte bleiben davon unberührt.
