# Frontend-Design und Analyse

Stadtplanner verwendet ein helles Civic-GIS-System. Die zentralen CSS-Variablen in
`frontend/app/assets/css/main.css` definieren Petrol/Türkis, Datenfarben, Oberflächen,
Rahmen, Radien und Schatten. Wiederverwendbare Oberflächen und Aktionen werden über
die Komponenten `Card`, `Button`, `IconButton`, `AppModal` und `AppBottomSheet`
gestaltet. Die lokale Basiskarte wird aus `frontend/scripts/build-map-style.mjs`
generiert und nutzt dieselbe ruhige Blau-Grau-/Grün-Palette.

## Diagramme

Die Diagramme verwenden Chart.js 4 mit vue-chartjs 5. Nur die tatsächlich benötigten
Bar-, Doughnut-, Skalen-, Legenden- und Tooltip-Module werden in
`frontend/app/utils/chartTheme.ts` registriert. Die Analysekomponenten werden in Nuxt
clientseitig und lazy geladen. Chart-Höhen sind begrenzt, Tabellen-Fallbacks und
Canvas-Labels machen die Kerndaten zugänglich; reduzierte Bewegung deaktiviert
Animationen.

Die kombinierte Analytics-Antwort liefert Branchen-, Größen-, Etagen-, Status- und
Betriebsformverteilungen sowie Datenvollständigkeit. Medianfläche, Leerstandsfläche
und flächenbezogene Leerstandsquote werden aus den gefilterten Geometrien berechnet.
Es werden keine Zeitreihen oder fehlenden Werte geschätzt.

## Filter- und Datenumfang

Alle Stadtplanner-Aggregate verwenden denselben zentralen GIS-Filterzustand wie die
Karte. Die Branchenübersicht ergänzt die deduplizierten OSM-Geschäftsobjekte des
aktuellen Kartenausschnitts. Datenquellen werden in der Oberfläche benannt; Größen-,
Etagen-, Status- und Qualitätsdaten sind ausdrücklich Stadtplanner-Fachdaten.
