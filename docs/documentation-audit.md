# Dokumentationsaudit

Stand: 20. August 2026

## Geprüfter Umfang

Geprüft wurden Root-, Backend- und Frontend-README, `CONTRIBUTING.md`, alle Dateien unter `docs/`, die öffentliche Dokumentationskonfiguration und ihre Komponenten, Frontend-Seiten und -Stores, Backend-API, Services, Schemas, Modelle und CLI-Module, Alembic-Migrationen, Environment-Beispiele, OSM-Skripte, systemd-Units und GitHub-Actions-Workflows.

## Ergebnis nach Themen

| Thema | Vorher | Maßnahme |
| --- | --- | --- |
| Karte, Filter und Flächendetails | vollständig bis teilweise | Begriffe vereinheitlicht und Verkaufsflächen gegenüber Gebäuden abgegrenzt |
| Intelligente Suche | fehlend im Benutzerhandbuch | öffentliche Seite mit Beispielen, Grenzen und Datenherkunft ergänzt |
| Analysegebiete | vollständig | öffentliche Erklärung beibehalten und mit Datenquellen verknüpft |
| OpenStreetMap | vollständig, teilweise zu technisch | Auffindbarkeit für Gebäude, POIs und Aktualität verbessert |
| Kommunale Statistik | teilweise in Methodik versteckt | eigene öffentliche Seite für Quelle, Periode, Zeitreihe und übergeordnete Werte ergänzt |
| Analytics und Kennzahlen | teilweise | Statistik, berechnete Auswertung und manuelle Referenzwerte klar getrennt |
| Leerstand und Datenqualität | verteilt und doppelt | zentrale öffentliche Definitionen und Korrekturwege ergänzt |
| Konto, Rollen und Bearbeitung | vollständig | Navigation unter „Konto und Bearbeitung“ zusammengeführt |
| Betrieb und Deployment | verteilt, teilweise doppelt | `deployment.md` als zentraler Einstieg ergänzt |
| Technische Orientierung | fehlend | `docs/README.md` als thematischer Index ergänzt |
| Mastodon-Betrieb | zu ausführlich im Root-README | in `social-publishing.md` ausgelagert |

## Behobene Drift und Widersprüche

- Der nicht vorhandene Verweis auf `SETUP.md` wurde entfernt.
- Für den Assistant wird die tatsächlich implementierte Variable `AI_SEARCH_MODEL` dokumentiert; ein nicht vorhandenes `GROQ_MODEL` wird nicht verwendet.
- Deployment beschreibt die abweichenden Pfade und Service-Benutzer der mitgelieferten systemd-Units, statt eine einheitliche Installation vorzutäuschen.
- Fehlende Werte, null und `UNKNOWN` werden getrennt erklärt.
- Kommunale Statistik wird nicht mehr mit aus Stadtplaner- oder OSM-Daten berechneten Analytics gleichgesetzt.
- Die öffentliche Methodik nennt keine internen SQL- oder Tabellenimplementierungen mehr als Voraussetzung zum Verständnis.

## Bekannte Restlücken

- Das Repository enthält keine produktive Nginx-Konfiguration und keine systemd-Unit für den dauerhaften API- oder Nuxt-Hauptprozess. Betreiber müssen diese plattformspezifisch bereitstellen.
- Die vorhandenen systemd-Units verwenden zwei unterschiedliche Installationspfade und Service-Benutzer. Vor Installation müssen sie an die reale Umgebung angeglichen werden.
- Ein allgemein garantierter Aktualisierungsrhythmus existiert nicht für alle Datenquellen; das Benutzerhandbuch verweist deshalb auf den jeweils sichtbaren Datenstand.

## Wartung

Bei jeder sichtbaren Kernfunktion sind öffentliche Hilfe, technische Dokumentation, Suchbegriffe und Tests gemeinsam zu prüfen. Ein Dokument darf Betriebsdetails nur zusammenfassen, wenn die spezialisierte Source-of-Truth-Dokumentation verlinkt bleibt.
