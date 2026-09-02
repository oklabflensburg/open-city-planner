# Sprachleitfaden für den Stadtplaner

## 1. Ansprache

Die öffentliche Anwendung verwendet bei direkter Ansprache konsequent die förmliche Sie-Form: „Sie“, „Ihr“, „Ihre“ und „Ihnen“. Der Stadtplaner richtet sich an Verwaltung, Wirtschaft, Zivilgesellschaft sowie interessierte Bürgerinnen und Bürger.

Wenn eine direkte Ansprache keinen Mehrwert bietet, ist eine neutrale Formulierung vorzuziehen. Beispielsweise ist „Für diese Funktion ist eine Anmeldung erforderlich“ klarer als eine persönliche Aufforderung.

## 2. UI-Aktionen und Zustände

Schaltflächen bleiben kurz und benennen die Aktion: „Speichern“, „Gebiet hinzufügen“, „Fläche löschen“ oder „Vorschau öffnen“. Systemzustände sind neutral: „Änderungen gespeichert“, „Daten werden geladen …“ oder „Veröffentlichung fehlgeschlagen“.

## 3. Formulare

Labels verwenden eindeutige Substantive wie „Titel“, „Adresse“, „E-Mail-Adresse“ und „Passwort“. Platzhalter enthalten möglichst Beispiele statt vollständiger Anweisungen. Hilfetexte sind neutral oder verwenden die Sie-Form und enden als vollständige Sätze mit einem Punkt.

## 4. Fehler und Bestätigungen

Fehler beschreiben das Problem konkret, respektvoll und ohne Schuldzuweisung: „Bitte geben Sie eine gültige E-Mail-Adresse ein“ oder „Die Fläche konnte nicht gespeichert werden“. Bestätigungsdialoge verwenden „Möchten Sie …?“ und keine informelle Rückfrage.

Erfolgsmeldungen sind kompakt und neutral: „Änderungen gespeichert“, „Fläche übernommen“ oder „Konto deaktiviert“.

## 5. Benachrichtigungen

Persönliche Zuordnungen verwenden die Sie-Form, etwa „Ihr Konto wurde wieder aktiviert“. Objektbezogene Ereignisse bleiben möglichst neutral. Aktionen zum Abonnieren heißen „Dieser Fläche folgen“, „Diesem Gebiet folgen“ und „Nicht mehr folgen“.

## 6. Authentifizierung und Konto

Login, Registrierung, Passwort-Wiederherstellung und Kontoverwaltung verwenden die förmliche Ansprache. Wo kurze Navigationstitel genügen, werden „Profil“, „Konto“ und „Einstellungen“ statt persönlicher Formulierungen verwendet.

## 7. GIS und öffentliche Seiten

Kartenaktionen, Filter, Layer und Tooltips verwenden überwiegend neutrale Funktionsbezeichnungen. Anleitungen verwenden die Sie-Form. Externe Namen, OpenStreetMap-Tags, Wikipedia-Titel und GeoJSON-Inhalte werden nicht sprachlich verändert.

## 8. Administration und Historie

Administrationshilfen verwenden neutrale Sprache oder die Sie-Form. Auditlog und Systemereignisse bleiben objektiv, beispielsweise „Rolle VERWALTUNG wurde zugewiesen“. Maschinenlesbare Rollen, Enumwerte, Eventtypen und Fehlercodes werden nicht umbenannt.

## 9. Dokumentation und Rechtstexte

Öffentliche Anleitungen verwenden die Sie-Form. Entwicklerdokumentation bleibt sachlich-neutral. Rechtstexte werden nicht aus stilistischen Gründen inhaltlich umgeschrieben; ihre rechtliche Bedeutung hat Vorrang.

## 10. Technische Begriffe und Typografie

Etablierte Begriffe wie API, OpenStreetMap, Wikipedia, GeoJSON und JWT bleiben erhalten. In der deutschen UI werden typografische Anführungszeichen („…“), die Ellipse (…) sowie deutsche Zahlen-, Datums- und Zeitformate verwendet.

## Glossar

| Begriff | Verwendung |
|---|---|
| Stadtplaner | Offizieller Produktname |
| Fläche | Fachlich gepflegte, räumlich abgegrenzte Fläche |
| Verkaufsfläche | Fläche mit Einzelhandels- oder Marktkontext |
| Standort | Stadtplaner-Fläche oder passend ausgewiesener POI im Standortkontext |
| Gebiet | Oberbegriff für Gemeinde, Stadtteil und Quartier |
| Gemeinde | Kommunale Gebietsebene |
| Stadtteil | Gebietsebene unterhalb der Gemeinde |
| Quartier | Kleinräumige Gebietsebene |
| Kennzahl | Berechneter oder gepflegter Analysewert |
| Vergleich | Gegenüberstellung konkreter Gebiete |
| Leerstand | Fläche mit fachlich bekanntem Leerstandsstatus |
| Filialisierung | Anteil bekannter Filialbetriebe |
| Betriebsform | Filialist, inhabergeführt oder unbekannt |
| Datenquelle | Herkunft einer dargestellten Information |
| Benachrichtigung | Fachlicher Hinweis innerhalb der Anwendung |
| Veröffentlichung | Öffentliche Ausgabe eines freigegebenen Ereignisses |
| Freigabe | Administrative Bestätigung vor einer Veröffentlichung |

## Automatisches Audit

`pnpm audit:language` prüft die nutzersichtbaren Frontend-, Backend-, Mail- und Dokumentationsressourcen auf informelle Pronomen und typische informelle Imperative. Markdown-Codeblöcke werden ausgelassen, damit Shell-Befehle wie `du -sh` nicht als Ansprache gelten. Treffer werden immer kontextbezogen korrigiert; das Audit führt keine automatischen Ersetzungen aus.
