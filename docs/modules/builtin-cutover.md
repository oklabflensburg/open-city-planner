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

Für `analysis-areas` ist der geprüfte externe Contract auf Commit
`71815f0396ec8bea545588fd8978dc78b284331a` gepinnt. Er liefert die Revisionen
`20260814_0014`, `20260817_0023`, `20260818_0025` und `20260819_0032` mit
unveränderten Kanten. Der isolierte Legacy-Adapter greift weiterhin auf reviewte
Host-Services zu. Das ist kein neuer Trust-Zustand, weil installierte In-Process-
Module bereits Trusted Code sind; der Cutover weitet diese privaten Imports nicht
aus und erfindet keine Analysis-Areas-spezifischen Platform-Ports.

## Rollback

1. Externes Modul deaktivieren und einen neuen Deployzustand rendern.
2. Vorherige Composition und bei Bedarf den vorherigen Host-Release bewusst
   wiederherstellen.
3. Backend und Frontend gemeinsam redeployen und Smokes wiederholen.

Rollback ändert die Alembic-Historie nicht, führt historische Revisionen nicht
erneut aus und startet keinen automatischen Downgrade.
