# Built-in-Modul kontrolliert externalisieren

Dieser Ablauf wählt für eine stabile Modul-ID genau eine Composition Source. Er
verwendet den vorhandenen `.ocp`-Installer, `modules.lock`, passive Migration
Discovery und den normalen Nuxt-Build. Es gibt keinen automatischen Fallback.

## Konfiguration

```env
OCP_EXCLUDED_BUILTIN_MODULES=analysis-areas
```

Die Liste ist generisch, komma-separiert und auf beiden Host-Seiten identisch.
Whitespace wird entfernt; ungültige, doppelte und unbekannte IDs stoppen den
Preflight. Ansible liest den Wert einmal aus dem geschützten Backend-Environment,
lässt ihn durch `modules env` validieren und bindet denselben Wert in Backend- und
Frontend-Snapshot ein. Aktivierung bleibt ausschließlich in `modules.lock`.

## Cutover-Runbook

1. Reviewtes, auf einen vollständigen Source-Commit zurückführbares `.ocp`
   bereitstellen und mit `modules verify` prüfen.
2. Mit `modules install` installieren. `list` muss `kind=installed` und
   `enabled=false` zeigen; der Runtime-Backend-Pfad muss leer bleiben.
3. Installierte Migrationsquelle und exklusiven globalen Graphen prüfen. Vor einer
   Ownership-Änderung müssen überlappende Dateien bytegleich sein; doppelte Quellen
   müssen bis dahin fehlschlagen.
4. Exclusion im Backend-Deploymentinput setzen und Target Release deployen. Im
   disabled Zustand ist der Built-in abwesend, die externe Runtime inaktiv und die
   externe Migration History weiterhin discoverbar.
5. `modules enable <id>` ausführen, den gerenderten Zustand deployen,
   Migrations-Preflight/Upgrade ausführen und Backend neu starten.
6. Backend-Inventar erzeugen, Frontend mit dem installierten Root bauen und API-,
   Daten-, SSR-, Route- und Map-Smokes ausführen.
7. Einmal `disable`, Deploy/Restart, passive Migration Discovery und anschließend
   `enable` mit erneutem Deploy/Restart prüfen.

Für `analysis-areas` ist der vollständige externe Release als v1.5.1 mit SHA-256
`8fd4b21c2da820f2d036f126848293395d4da772201f8473c07c0ef38e068bc9`
und Source-Commit `e190c4c5a70df6dbbe1f538f82e68d30260fe071` gepinnt. Er liefert die Revisionen
`20260814_0014`, `20260817_0023`, `20260818_0025` und `20260819_0032` mit
unveränderten Kanten. Seine Host-Capabilities sind vollständig in
[öffentliche Backend-Service-Ports](backend-service-ports.md) inventarisiert.
Das Paket importiert ausschließlich das öffentliche SDK; Gebietsfachlogik und
Persistenz bleiben im Modul.

Der Registry-Cutover-Contract prüft den produktiven Flow: Das externe
Modul löst Gebiet und `polygon_analysis_areas` über seine eigenen ORM-Modelle und
den bestehenden `DatabaseSessionProvider` auf, baut daraus einen neutralen
`PolygonScope` und ruft erst danach den Host-Polygon-Port auf. Die
Statistikhierarchie wird ebenso vor dem neutralen Host-Port im Modul aufgelöst.
Die Registry-Version 1.0.0 bleibt ein gültiger Installer-/Migrations-Pin, ist aber
mit dem aktuellen `ModuleContext` nicht backend-runtime-kompatibel und enthält
noch nicht die später ergänzte OSM-/Wikidata-/Polygon-Parität. Details und die
klare Grenze zum finalen Produktionsnachweis stehen im
[Host-Cleanup-Nachweis](analysis-areas-host-cleanup.md).

## Rollback

1. Externes Modul deaktivieren und einen neuen Deployzustand rendern.
2. Vorherige Composition und bei Bedarf den vorherigen Host-Release bewusst
   wiederherstellen.
3. Backend und Frontend gemeinsam redeployen und Smokes wiederholen.

Rollback ändert die Alembic-Historie nicht, führt historische Revisionen nicht
erneut aus und startet keinen automatischen Downgrade.
