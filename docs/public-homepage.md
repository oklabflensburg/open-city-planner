# Öffentliche Startseite und Kartenlinks

Die öffentliche Informationsarchitektur trennt auffindbare Inhalte von der interaktiven GIS-Anwendung:

- `/` ist ein serverseitig gerendertes Verzeichnis für öffentliche Flächen.
- `/karte` enthält die bestehende GIS-AppShell.
- `/flaechen/<slug>` ist das kanonische Host-Detaildokument. Weitere öffentliche Dokumente werden von Modulen beigetragen.

Die Startseite lädt Listing-Daten in Seiten über `GET /api/v1/polygons/directory?offset=<n>&limit=<n>`. Der Directory-Vertrag enthält ausschließlich Slug, Name, Kategorie, Etage, öffentliche Adresse, Belegungsstatus, Betriebsform und `updated_at`. Geometrie, Benutzer-, Eigentümer-, Preis- und Verwaltungsdaten sind ausgeschlossen. `next_offset` steuert das Chunking; die GIS-Grenze von 1.000 Einträgen ist keine fachliche Grenze des Verzeichnisses.

Karten-UI-Zustände verwenden:

- `/karte?flaeche=<slug>` für eine öffentliche Fläche.

Die Karte lädt die Fläche bei Bedarf über ihren Slug nach und nutzt anschließend dieselben Stores, Overlays und Detailverweise wie eine manuelle Auswahl. Der etablierte Parameter `polygon=<uuid>` funktioniert auf `/karte` weiter. Modulparameter und Deep Links werden von den jeweiligen Contributions interpretiert. Der Canonical aller Karten-Queryzustände bleibt `/karte`.

Vorschaubilder und deren Cache sind in [Serverseitige Kartenvorschauen](map-previews.md) beschrieben.
