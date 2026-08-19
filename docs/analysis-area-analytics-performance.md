# Performance der Gebiets-Analytics prüfen

Die POI-Auswertung verwendet `ST_PointOnSurface(osm.geometry)`, damit auch Linien und Flächen über einen repräsentativen Punkt einem Analysegebiet zugeordnet werden. Dieser Ausdruck kann den vorhandenen GiST-Index auf `osm_features.geometry` nicht direkt verwenden. Ohne räumlichen Vorfilter muss PostgreSQL den Punkt deshalb unter Umständen für einen großen Teil des lokalen OSM-Bestands berechnen.

Die Abfrage begrenzt die Kandidaten nun zuerst mit `osm.geometry && target.geometry`. Dieser Bounding-Box-Operator ist über den GiST-Index indexierbar. Erst für die verbleibenden Kandidaten wird `ST_PointOnSurface` berechnet und mit `ST_Covers` exakt geprüft. Ein CTE lädt die Zielgeometrie nur einmal.

Zusätzlich enthält Migration `20260819_0032` den partiellen GiST-Index `idx_osm_features_poi_geometry`. Er umfasst nur Datensätze mit `shop`, `amenity`, `tourism` oder `leisure`. Der unveränderte allgemeine Index `idx_osm_features_geometry` bleibt für andere räumliche Abfragen bestehen. Ein vorberechnetes `poi_point` wurde nicht eingeführt: Der Bounding-Box-Vorfilter behebt den fehlenden Indexzugriff ohne zusätzliche Spalte, Importlogik oder redundante Geometriedaten.

## Query-Plan vergleichen

Die Datei [`analysis-area-analytics-explain.sql`](./analysis-area-analytics-explain.sql) kann mit einer vorhandenen internen numerischen Gebiets-ID ausgeführt werden:

```bash
psql "$DATABASE_URL" -v area_id=123 -f docs/analysis-area-analytics-explain.sql
```

Bei einem produktionsähnlichen Datenbestand sind insbesondere folgende Werte zu vergleichen:

- Zugriff über `idx_osm_features_poi_geometry` oder `idx_osm_features_geometry` statt eines vollständigen sequenziellen Scans,
- Anzahl der vom Bounding-Box-Filter gelieferten Kandidaten,
- `Rows Removed by Filter` bei der anschließenden `ST_Covers`-Prüfung,
- tatsächliche Laufzeit sowie gemeinsam gelesene beziehungsweise bereits gepufferte Blöcke.

Der konkrete Plan hängt von Gebietsgröße, Tag-Verteilung, Tabellenstatistik und Datenmenge ab. Deshalb werden keine nicht gemessenen Laufzeitwerte festgehalten. Nach einem großen OSM-Import sollte PostgreSQL aktuelle Statistiken besitzen; bei Bedarf kann `ANALYZE osm_features` vor dem Vergleich ausgeführt werden.

Das öffentliche `statement_timeout` von acht Sekunden bleibt als Schutzgrenze bestehen. SQLSTATE `57014` wird für Analytics-Endpunkte kontrolliert in HTTP 503 mit dem Fehlercode `ANALYTICS_QUERY_TIMEOUT` übersetzt; die fehlgeschlagene Read-only-Transaktion wird vorher zurückgerollt.
