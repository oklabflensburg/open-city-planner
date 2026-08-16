# Kommunale Statistik aus dem Flensburger Zahlenspiegel

## Discovery vom 16. August 2026

Quelle ist das veröffentlichte Dashboard „Zahlenspiegel“ der Stadt Flensburg:

`https://superset.flensburg.de/superset/dashboard/3b53ff0b-6e8c-435e-83f6-666f8a7cc158/`

Die Instanz meldet Apache Superset `4.0.2`. Dashboard-ID `16`, angefragte UUID `3b53ff0b-6e8c-435e-83f6-666f8a7cc158`, veröffentlicht, ohne Slug. Das Dashboard nennt Datenstand `31.12.2025`, letzte redaktionelle Aktualisierung `18.05.2026`, Melderegister als Datenquelle und „Datenlizenz Deutschland – Zero – Version 2.0“. Der technische Dashboard-Datensatz wurde zuletzt am 6. August 2026 geändert.

Die öffentlichen REST-Aufrufe `GET /api/v1/dashboard/{uuid}`, `/charts` und `/datasets` funktionieren anonym. Daten werden strukturiert mit `POST /api/v1/chart/data` abgefragt. `result_format=json` liefert JSON und `result_format=csv` eine UTF-8-CSV mit `Content-Type: text/csv`; Authentifizierung, Gasttoken und CSRF-Token sind dafür aktuell nicht erforderlich. Der gespeicherte Chart-Endpunkt `GET /api/v1/chart/{id}/data/` ist für diese Charts nicht nutzbar, weil kein Query-Context gespeichert ist. Der Importer verwendet deshalb die dokumentierte Chart-Data-API mit den veröffentlichten Dataset-IDs und Spalten, nicht Dashboard-HTML oder DOM-Scraping.

## Chart-Inventar

Das Dashboard enthält 27 Charts ohne Tabs. Mehrere Charts visualisieren dieselben fünf normalisierten Datasets:

| IDs | Veröffentlichte Charts | Dataset |
| --- | --- | --- |
| 46, 124, 125, 128–132, 202, 203 | Bevölkerung, nicht deutsche Bevölkerung, Altersgruppen, Familienstand und Stadtteile | 6 `STK_RESULTS_Sozialatlas_01` |
| 126, 140–143, 201, 204 | Haushalte, Haushaltsgrößen und Stadtteile | 7 `STK_RESULTS_Haushalte_AnzahlPersonenHaushalt` |
| 127, 136–138 | Haushalte nach Migrationshintergrund und Stadtteilen | 8 `STK_RESULTS_Haushalte_Migrationshintergrund` |
| 196–200 | Haushalte nach Kinderzahl und Stadtteilen | 9 `STK_RESULTS_Haushalte_ZahlKinderHaushalt` |
| 134 | als Haushaltstyp bezeichnete Gesamtzeitreihe | 10 `STK_RESULTS_Haushalte_Haushaltstyp` |

Reale Dimensionen sind Jahr, Wohnstatus, Stadtteilname sowie je nach Dataset Migrationshintergrund, Altersgruppe, Familienstand, Personen- oder Kinderzahl. Die Zeitreihe umfasst 2011 bis 2025. Dataset 10 veröffentlicht über die API keine Haushaltstyp-Dimension und wird daher nicht als scheinbar detaillierte Kennzahl importiert.

## Importierte Kennzahlen

Alle Werte gelten für Stadtteile und die rechnerische Gesamtstadt, jeweils jährlich von 2011 bis 2025. Superset liefert ausschließlich Anzahlen; es werden keine Prozentwerte oder Quartierswerte abgeleitet.

| Keys | Kennzahlen | Einheit |
| --- | --- | --- |
| `population`, `population_non_german` | Bevölkerung gesamt, nicht deutsche Bevölkerung | Personen |
| `population_age_0_17`, `population_age_18_64`, `population_age_65_plus` | drei Altersgruppen | Personen |
| `population_marital_single`, `_married`, `_divorced`, `_widowed`, `_other`, `_unknown` | sechs Familienstandsgruppen | Personen |
| `households`, `households_non_german` | Haushalte gesamt, nicht deutsche Haushalte | Haushalte |
| `households_size_1` bis `_4`, `households_size_5_plus` | fünf Haushaltsgrößen | Haushalte |
| `households_children_1` bis `_3`, `households_children_4_plus` | vier Kinderzahlgruppen | Haushalte |

## Gebiete und Mapping

Superset liefert genau 13 Namen, aber keinen stabilen Gebietsschlüssel. Die amtlichen Stadtteilnummern aus den Zahlenspiegel-Veröffentlichungen werden deshalb in `external_area_mappings` explizit hinterlegt:

| ID | Superset-Name | Stadtplaner-Typ |
| --- | --- | --- |
| 00 | Flensburg (rechnerische Summe) | MUNICIPALITY |
| 01 | Altstadt | DISTRICT |
| 02 | Neustadt | DISTRICT |
| 03 | Nordstadt | DISTRICT |
| 04 | Westliche Höhe | DISTRICT |
| 05 | Friesischer Berg | DISTRICT |
| 06 | Weiche | DISTRICT |
| 07 | Südstadt | DISTRICT |
| 08 | Sandberg | DISTRICT |
| 09 | Jürgensby | DISTRICT |
| 10 | Fruerlund | DISTRICT |
| 11 | Mürwik | DISTRICT |
| 12 | Engelsby | DISTRICT |
| 13 | Tarup | DISTRICT |

Der Import akzeptiert nur die vollständige Menge `13 mapped / 0 unmapped / 0 ambiguous`. Ein unbekannter oder fehlender Name bricht den Lauf vor dem Beobachtungs-Upsert ab. Die vorhandenen `analysis_areas` enthalten dieselben 13 Stadtteile als OSM-Relationen. Eine geometrisch exakte Identität der OSM-Grenzen mit der kommunalen Statistikgeografie ist durch Superset nicht belegbar und wird weder technisch noch öffentlich behauptet. Die Statistik wird dem fachlichen Stadtteilbegriff zugeordnet; Kartenflächen bleiben als OSM-Grenzen gekennzeichnet.

Quartiere erhalten keine künstlich verteilten Beobachtungen. Ihre API-Antwort verweist ausdrücklich auf den gemappten Parent-Stadtteil und kennzeichnet dessen Werte als `inherited_from_parent`.

## Import und Betrieb

Manuelle Discovery:

```bash
cd backend
.venv/bin/python -m app.cli.import_flensburg_statistics --discover-only
```

Import:

```bash
cd backend
.venv/bin/alembic upgrade head
.venv/bin/python -m app.cli.sync_analysis_areas --municipality Flensburg
.venv/bin/python -m app.cli.import_flensburg_statistics
```

Der Statistikimport setzt die Gemeinde und alle 13 Stadtteile in `analysis_areas` voraus. Auf einer neuen Installation muss daher zuerst der lokale OSM-Bestand in `osm_features` geladen und anschließend `sync_analysis_areas` ausgeführt werden. Fehlen diese Gebiete, endet der Lauf mit `FAILED`, ohne vorhandene Statistikdaten zu verändern.

Der Import prüft HTTP-Status, Content-Type, UTF-8/BOM, Trennzeichen, exakte Header, Perioden, Zahlenwerte, Dashboard-Inventar und Gebietsmapping. Er schreibt Zeitreihen per Unique-Key-Upsert, erhält frühere Jahre und protokolliert Lauf, Schemahash und SHA-256-Checksumme. Bei Fehlern bleiben alle zuletzt erfolgreich importierten Beobachtungen bestehen. Unterdrückte Werte werden als NULL gespeichert und nicht zu null oder aus anderen Zellen zurückgerechnet.

Die Quelle wird inhaltlich jährlich aktualisiert. Der mitgelieferte systemd-Timer prüft deshalb wöchentlich; identische Beobachtungen bleiben unverändert. Nach Erfolg werden nur `statistics` und `analysis-areas` versioniert und ein einzelnes System-Auditereignis geschrieben.

Roh-CSV-Dateien werden weder archiviert noch committed. Das bereits ignorierte Verzeichnis `data/` kann bei Bedarf für ein extern geregeltes Betriebsarchiv genutzt werden.

Der verifizierte Import vom 16. August 2026 lud 14.001 strukturierte Quellzeilen und erzeugte 4.564 normalisierte Beobachtungen für 22 Kennzahlen. Der unmittelbar wiederholte Lauf meldete `0 inserted / 0 updated / 4564 unchanged`; SHA-256: `156cd199f1d0b8370390cb8ed984f8d56a6bb18370dda9e664a8aa6904ba2dad`.

Browserprüfung:

```bash
cd frontend
pnpm test:e2e
```

Die Playwright-Suite startet Backend und Nuxt lokal und prüft Gemeinde, Stadtteil und Quartier einschließlich SSR-Inhalt, mobiler Parent-Kennzeichnung und ausbleibender Browserzugriffe auf Superset.
