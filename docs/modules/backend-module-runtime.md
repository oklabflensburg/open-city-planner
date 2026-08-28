# Backend-Module-Runtime

Die erste Module Runtime ergänzt den bestehenden FastAPI-Host während der
inkrementellen Migration aus
[ADR #92](../architecture/adr-modular-host-and-module-boundaries.md). Sie verwendet
den bestehenden [Manifest-V1-Contract](module-manifest-v1.md) für Parsing,
Compatibility, Dependencies und deterministische Load Order. Der zentrale Legacy-
Router bleibt parallel eingebunden; keine bestehende Fachdomäne wurde migriert.

## Bootstrap und Enablement

`backend/app/main.py` erzeugt eine fachneutrale Runtime aus zwei Discovery-Providern
und bindet deren Router zusätzlich zum Legacy-Router ein. `ENABLED_MODULES` enthält
eine komma-separierte Liste aktivierter Modul-IDs. Der leere Default aktiviert kein
neues Modul und bewahrt damit das bisherige Produktionsverhalten.

Die API-Version aus `Settings.api_version` ist gleichzeitig die zentral gepflegte
Host-Kompatibilitätsversion. Die öffentliche Backend-SDK-Version steht unabhängig
davon als `MODULE_SDK_VERSION` in der Runtime. Release-SHA, Host-Version und
SDK-Version sind unterschiedliche Werte.

Aktivierung ist in dieser Ausbaustufe ausschließlich deploy-time Konfiguration. Ein
aktiviertes, aber nicht auffindbares Modul stoppt den Bootstrap. Deaktivierte Module
werden weder importiert noch instanziiert und stehen der Dependency-Auflösung nicht
zur Verfügung. Dadurch schlägt eine Required Dependency auf ein deaktiviertes Modul
mit der bestehenden Manifest-Fehlersemantik fehl. Eine optionale Dependency darf
weiterhin fehlen.

## Generiertes Backend-Inventar

`resolve_module_definitions()` ist zugleich die einzige Quelle für das technische
Frontend-Inventar. Die CLI projiziert ausschließlich ID und Version der bereits
aktivierten, validierten Manifeste; sie führt keine zweite Discovery und lädt keinen
Modul-Runtimecode:

```bash
cd backend
uv run python -m app.cli.module_inventory --format json
uv run python -m app.cli.module_inventory --format env
```

JSON ist der stabile Maschinenvertrag, zum Beispiel
`{"modules":[{"id":"analysis-areas","version":"1.0.0"}]}`. Das env-Format
`analysis-areas@1.0.0` bleibt ein interner Transport zum vorhandenen Nuxt-Preflight.
Bei leerem `ENABLED_MODULES` enthält JSON eine leere `modules`-Liste und das
env-Format ist leer. Die Reihenfolge entspricht der deterministischen, aufgelösten
Dependency-/Load-Reihenfolge.

Trust und Capabilities werden bewusst nicht in diesen Build-Contract gemischt. Das
Kompatibilitätsinventar bleibt auf ID und Version begrenzt.

Runtime-, Dependency- und Jobdiagnose bleibt davon getrennt und wird ausschließlich
als geschützter, read-only [operationaler Modulstatus](operations.md) aus der
laufenden Runtime projiziert.
Enable, Disable, Re-Enable und Fehler-Recovery sind in der zentralen
[Lifecycle-Policy](lifecycle.md) verbindlich beschrieben.

## Discovery-Quellen

`FirstPartyModuleDiscovery` lädt ausschließlich explizit aktivierte Built-ins nach
der Repository-Konvention `backend/app/modules/<python_name>/module.py` mit dem
passiven Export `DEFINITION`. Die öffentliche Kebab-Case-ID wird dabei
deterministisch in einen Python-Namen mit Unterstrichen übersetzt. Ein neues
First-Party-Modul benötigt dadurch weder einen zentralen Entry-Point-Eintrag noch
eine Änderung an `main.py` oder `app/api/router.py`.

`EntryPointModuleDiscovery` berücksichtigt ausschließlich die Python-Entry-Point-
Gruppe `open_city_planner.modules`. Der Entry-Point-Name ist die aktivierbare
Modul-ID. Nur Entry Points mit explizit aktivierter ID werden geladen; andere
Gruppen und deaktivierte Einträge werden nicht ausgeführt. Ein Entry Point exportiert
eine passive `ModuleDefinition`, deren Manifest vor dem eigentlichen Modul-Loader
geprüft wird. Distribution und Installation werden von dieser Runtime nicht
verändert. Third-Party-Review und Integrität gehören vor diesen Schritt an die
Installer-/Deploymentgrenze (#173 und #174). Namen und Release-Metadaten
installierbarer Artefakte definiert die [Distribution Policy](distribution.md);
die Runtime leitet daraus keine Modul-ID ab.
Der [Installer](installer.md) stellt zusätzliche Python-Distributionen in einer
host-owned Ablage bereit. Sein generierter
`OCP_ENABLED_INSTALLED_BACKEND_PATHS`-Wert enthält ausschließlich aktivierte
installierte Module; `ENABLED_MODULES` bleibt die konkrete Runtime-Auswahl für den
nächsten Prozessstart. Der Discovery-Konstruktor verändert `sys.path` nicht.
Entry-Point-Metadaten aus zusätzlichen Roots werden explizit über
`importlib.metadata.distributions(path=...)` gelesen und der tatsächliche Load läuft
mit einem scoped, vollständig wiederhergestellten Python-Pfad. Erst die
Runtime-Komposition hängt aktivierte Roots dauerhaft hinter Host-Code und
Venv-Dependencies an. Deaktivierte installierte Module erhalten keinen
Runtime-Importpfad.

## Registrierungs- und Lifecycle-Reihenfolge

Der Ablauf ist strikt getrennt:

1. Definitionen aktivierter Module entdecken;
2. Manifeste über `parse_manifest()` und `validate_manifests()` prüfen;
3. Reihenfolge über `resolve_module_order()` bestimmen;
4. validierte Module instanziieren;
5. deklarative Router- und Lifecycle-Beiträge registrieren;
6. Startup-Hooks in Load Order ausführen;
7. Shutdown-Hooks in umgekehrter Reihenfolge ausführen.

Die Runtime erzeugt pro validiertem Manifest einen unveränderlichen, modulgebundenen
[`ModuleContext`](backend-module-sdk.md). Seine API- und Lifecycle-Registrare nutzen
intern weiterhin den kleinen `ModuleRegistrationContext` aus #94. Datenbank, Cache,
Storage, Events, Services und Jobs werden ausschließlich über die öffentlichen Ports
des SDK angeboten. Capabilities stammen unverändert aus dem Manifest und sind über
`ModuleRegistry.capabilities(module_id)` verfügbar.
Permissions aktiver Module werden aus demselben Manifest in die hostseitige
`PermissionRegistry` übernommen. Die Runtime versiegelt sie nach der deklarativen
Registrierung; deaktivierte Module hinterlassen keine aktive Permission.

`ModuleRuntime.register(app)` darf genau einmal aufgerufen werden. Damit entstehen
keine stillen Router-Duplikate. `register()` ist für deklarative Beiträge bestimmt;
Verbindungen, Worker und andere externe Side Effects gehören in asynchrone Startup-
Hooks.

## Fehler und Cleanup

Manifest-, Compatibility- und Dependency-Fehler bleiben als verkettete Ursachen der
strukturierten Runtime-Fehler erhalten. Runtime-Fehler nennen die Phase
`discovery`, `validation`, `import`, `registration`, `startup` oder `shutdown` sowie
Modul-ID und Origin, soweit diese bekannt sind. Registrierungs- und Startup-Fehler
stoppen den Host fail-fast.

Schlägt ein Startup-Hook fehl, führt die Runtime die Shutdown-Hooks aller bereits
erfolgreich gestarteten Beiträge in umgekehrter Reihenfolge aus. Cleanup-Fehler
werden protokolliert, ohne den ursprünglichen Startup-Fehler zu verdecken. Beim
regulären Shutdown werden trotz eines einzelnen Hook-Fehlers die übrigen Beiträge
weiter beendet. Runtime-Logs tragen die strukturierten Felder `module_id`,
`module_version` und `module_phase`.

## Vertrauen und Sicherheit

Built-in- und geprüft installierte Third-Party-Module sind vertrauenswürdiger
In-Process-Code und nicht sandboxed. Capabilities und `ModuleContext` sind
Architekturverträge, keine Prozessisolation. Die Runtime installiert keine Pakete,
lädt keine URLs und akzeptiert keine Python-Modulnamen aus HTTP- oder sonstigen
Nutzereingaben. Aktivierte IDs und installierte Entry Points werden ausschließlich
durch Packaging und Deployment kontrolliert. Das
vollständige Modell steht in der
[Trust-ADR](../architecture/adr-module-trust-model.md).
