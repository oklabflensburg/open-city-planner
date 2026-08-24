# Öffentliche Startseite und Kartenlinks

Die öffentliche Informationsarchitektur trennt auffindbare Inhalte von der interaktiven GIS-Anwendung:

- `/` ist ein serverseitig gerendertes Verzeichnis für öffentliche Flächen, Stadtteile und Quartiere.
- `/karte` enthält die bestehende GIS-AppShell.
- `/flaechen/<slug>` und `/gebiete/<slug>` bleiben die kanonischen Detaildokumente.

Die Startseite lädt Analysegebiete ohne Geometrie über `GET /api/v1/analysis-areas` und alle Listing-Daten in Seiten über `GET /api/v1/polygons/directory?offset=<n>&limit=<n>`. Der Directory-Vertrag enthält ausschließlich Slug, Name, Kategorie, Etage, öffentliche Adresse, Belegungsstatus, Betriebsform, Gebietsnamen/-Slugs und `updated_at`. Geometrie, Benutzer-, Eigentümer-, Preis- und Verwaltungsdaten sind ausgeschlossen. `next_offset` steuert das Chunking; die GIS-Grenze von 1.000 Einträgen ist keine fachliche Grenze des Verzeichnisses.

Karten-UI-Zustände verwenden:

- `/karte?flaeche=<slug>` für eine öffentliche Fläche;
- `/karte?gebiet=<slug>` für ein Analysegebiet.

Die Karte lädt die Fläche bei Bedarf über ihren Slug nach und nutzt anschließend dieselben Stores, Overlays, Analysebereiche und Detailverweise wie eine manuelle Auswahl. Die etablierten Parameter `polygon=<uuid>` und `area=<slug>` funktionieren auf `/karte` weiter. Alte Root-Links werden permanent auf `/karte` umgeleitet; `area` wird dabei in `gebiet` übersetzt. Der Canonical aller Karten-Queryzustände bleibt `/karte`.

Vorschaubilder und deren Cache sind in [Serverseitige Kartenvorschauen](map-previews.md) beschrieben.
