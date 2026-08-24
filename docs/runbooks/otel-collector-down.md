# OpenTelemetry Collector nicht erreichbar

## Signal und Schwelle

`StadtplanerOtelCollectorDown` wird kritisch, wenn die lokale Health-URL des
verpflichtenden Collectors fünf Minuten lang nicht erfolgreich antwortet. Ein
Deployment prüft denselben Dienst vor der Release-Aktivierung und bricht bei
einem Fehler ab. Ein späterer Ausfall darf laufende API-Anfragen nicht
blockieren.

## Diagnose

Auf dem Applikationshost prüfen:

```bash
sudo systemctl status stadtplaner-otel-collector stadtplaner-tempo
sudo journalctl -u stadtplaner-otel-collector -n 200 --no-pager
sudo journalctl -u stadtplaner-tempo -n 200 --no-pager
curl --fail http://127.0.0.1:13133/health/status
curl --fail http://127.0.0.1:3200/ready
ss -ltn '( sport = :4317 or sport = :4319 or sport = :13133 or sport = :3200 )'
```

Port `4317` muss ausschließlich lokal den OTLP/gRPC-Receiver des Collectors
erreichen. Port `4319` verbindet den Collector intern mit Tempo. Health läuft
lokal auf `13133`; die Tempo-Abfrage- und Readiness-API auf `3200`. Keine dieser
Adressen darf über Nginx oder eine öffentliche Firewall-Regel publiziert sein.

Danach die API unabhängig prüfen:

```bash
curl --fail http://127.0.0.1:8008/health/live
curl --fail http://127.0.0.1:8008/health/ready
```

## Mitigation und Eskalation

1. Freien Speicher und Rechte von `/var/lib/stadtplaner-tempo` prüfen.
2. Zuerst Tempo, danach den Collector kontrolliert neu starten:

   ```bash
   sudo systemctl restart stadtplaner-tempo
   curl --fail http://127.0.0.1:3200/ready
   sudo systemctl restart stadtplaner-otel-collector
   curl --fail http://127.0.0.1:13133/health/status
   ```

3. Bei wiederholten Exportfehlern Collector- und Tempo-Konfiguration mit dem
   zuletzt erfolgreich deployten Commit vergleichen. Keine Traces durch einen
   Logging-Exporter mit potenziell sensiblen Attributen ersetzen.
4. Schlägt ein laufender Deploy im Trace-Smoke-Test fehl, dessen automatisches
   Symlink-Rollback abschließen lassen. Bei einem reinen Collector-Ausfall ist
   kein Anwendungsrollback nötig; die API bleibt bewusst fail-open.
5. Bleiben Collector oder Tempo instabil, Betriebsteam eskalieren und bis zur
   Behebung keine weiteren Produktionsreleases aktivieren.
