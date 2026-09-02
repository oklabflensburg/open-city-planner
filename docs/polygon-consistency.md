# Polygon API: Konsistenzmodell & Outbox

## Transaktionsgrenzen und Atomarität
Alle Mutationen an Polygonen (`create`, `update`, `delete`) garantieren die atomare Speicherung der Kernressource (`UserPolygon`) sowie zugehöriger Audit-Logs. Ein Fehler nach erfolgreicher Transaktion (z. B. durch Ausfall externer Dienste wie Nominatim) führt nicht mehr zu einer HTTP-500-Antwort für eine bereits dauerhaft gespeicherte Fläche.

## Seiteneffekte über Outbox
Externe und nichtkritische Seiteneffekte wurden von der synchronen Request-Verarbeitung entkoppelt. Sie werden als langlebige Aufträge in die Tabelle `polygon_outbox` geschrieben und asynchron abgearbeitet.
Dazu gehören:
- **Adressanreicherung (Nominatim)**: Löst nach erfolgreicher Adressfindung optional eine Aktualisierung des Polygon-Slugs aus.
- **Benachrichtigungen**: Nutzer und Subscriber werden nach Mutationen per E-Mail und In-App benachrichtigt.
- **Cache Invalidierung**: (Falls materialisierte Views oder externe Systeme asynchron bedient werden).

## Wiederholungsverhalten und Idempotenz
Die Polygon-Erstellung über `POST /polygons` unterstützt einen `idempotency_key` (Wiederholungsschutz). Wird ein Request mit demselben Idempotency Key wiederholt, gibt die API die bereits erstellte Fläche zurück (`201 Created` oder im Body erkennbar), ohne eine zweite Fläche oder doppelte Outbox-Events anzulegen.

## Monitoring
Der Cronjob/Worker `backend/app/cli/process_polygon_outbox.py` verarbeitet die Aufträge. Die Zustände der Outbox (`PENDING`, `PROCESSING`, `COMPLETED`, `FAILED`, `DEAD_LETTER`) können überwacht werden. Ein Auftrag wandert nach 8 fehlgeschlagenen Zustellversuchen mit exponentiellem Backoff in den `DEAD_LETTER` Zustand.
