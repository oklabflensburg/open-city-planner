# Built-in-Modul kontrolliert externalisieren

Dieser Ablauf wählt für eine stabile Modul-ID genau eine Composition Source. Er
verwendet den vorhandenen `.ocp`-Installer, `modules.lock`, passive Migration
Discovery und den normalen Nuxt-Build. Es gibt keinen automatischen Fallback.

## Konfiguration

Für `analysis-areas` bleibt `OCP_EXCLUDED_BUILTIN_MODULES` nach dem finalen
Source-Cutover leer. Die frühere Exclusion war nur für den Release mit parallel
vorhandenem Built-in bestimmt; nach dessen physischer Entfernung wäre sie eine
ungültige Unknown-Exclusion und würde den Preflight absichtlich stoppen.

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
4. Target Release ohne die frühere `analysis-areas`-Exclusion deployen. Im
   disabled Zustand ist keine Domain-Runtime aktiv; die externe Migration History
   bleibt dennoch discoverbar.
5. `modules enable <id>` ausführen, den gerenderten Zustand deployen,
   Migrations-Preflight/Upgrade ausführen und Backend neu starten.
6. Backend-Inventar erzeugen, Frontend mit dem installierten Root bauen und API-,
   Daten-, SSR-, Route- und Map-Smokes ausführen.
7. Einmal `disable`, Deploy/Restart, passive Migration Discovery und anschließend
   `enable` mit erneutem Deploy/Restart prüfen.

Für `analysis-areas` ist der geprüfte externe Contract auf den PR-#2-Merge-Commit
`06afb05fed5dab8426e0e52392d3716ba46c980a` gepinnt. Er liefert die Revisionen
`20260814_0014`, `20260817_0023`, `20260818_0025` und `20260819_0032` mit
unveränderten Kanten. Der Merge-Stand importiert ausschließlich das öffentliche
Backend-SDK 1.9; private Host-Imports und der frühere Legacy-Adapter sind entfernt.

Der Cross-Repo-Contract prüft den produktiven Folgeflow: Das externe
Modul löst Gebiet und `polygon_analysis_areas` über seine eigenen ORM-Modelle und
den bestehenden `DatabaseSessionProvider` auf, baut daraus einen neutralen
`PolygonScope` und ruft erst danach den Host-Polygon-Port auf. Der Host behält
dabei ausschließlich generische Plattform- und Nachbardomain-Ports.

## Rollback

1. Den vorherigen Host-Release beziehungsweise Host-Commit bewusst
   wiederherstellen; es existiert kein automatischer Built-in-Fallback.
2. Den dazugehörigen Modulzustand rendern und Backend und Frontend gemeinsam
   redeployen.
3. Smokes wiederholen.

Rollback ändert die Alembic-Historie nicht, führt historische Revisionen nicht
erneut aus und startet keinen automatischen Downgrade.
