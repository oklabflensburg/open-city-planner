# Namespacete Modulkonfiguration

Die Modulkonfiguration setzt die Host-/Modulgrenze aus
[ADR #92](../architecture/adr-modular-host-and-module-boundaries.md) um. Neue
Fachmodule erweitern nicht die zentrale `app.core.config.Settings`-Klasse. Sie
besitzen ein typisiertes, unveränderliches Pydantic-Schema und erhalten genau dieses
Schema über `ModuleContext.settings`.

## Environment-Namespace

Die einzige dauerhafte Konvention lautet:

```text
OCP_MODULE_<MODULE-ID>_<SETTING>
```

Modul-IDs stammen aus dem Manifest, sind lowercase Kebab Case und werden
deterministisch in Großbuchstaben mit Unterstrichen übersetzt:

| Modul-ID | Environment-Präfix |
| --- | --- |
| `analysis-areas` | `OCP_MODULE_ANALYSIS_AREAS_` |
| `analysis2` | `OCP_MODULE_ANALYSIS2_` |
| `a-b-c` | `OCP_MODULE_A_B_C_` |

Unterstriche sind in Manifest-Modul-IDs nicht erlaubt. Deshalb kollidiert die
Transformation nicht mit einer zweiten ID-Schreibweise. `config.namespace` im
Manifest muss der Modul-ID entsprechen und wird nicht durch ein paralleles
Runtime-Namespace ersetzt.

## Schema und Contribution

Settings-Schemas liegen beim owning module. V1 verwendet flache Environment-Felder;
nested Pydantic-Modelle können intern genutzt werden, erhalten aber keine eigene
Environment-Namenskonvention. Modelle müssen `frozen=True` verwenden, damit nach der
einmaligen Startup-Validierung keine Runtime-Mutation möglich ist.

```python
from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, SecretStr

from app.platform.modules.sdk import ModuleSettingsContribution


class BiotopesSettings(BaseModel):
    api_url: AnyHttpUrl = Field(json_schema_extra={"public": True})
    timeout_seconds: int = 10
    api_token: SecretStr

    model_config = ConfigDict(frozen=True)


SETTINGS = ModuleSettingsContribution(
    module_id="biotopes",
    namespace="biotopes",
    model=BiotopesSettings,
)
```

Die passive Contribution hängt wie Persistence-Metadaten an der
`ModuleDefinition`. Der Host kann sie dadurch vor dem Laden des Modul-Runtimecodes
validieren. Manifest, Contribution und owning module müssen exakt übereinstimmen.

## Defaults, Required und Overrides

Pydantic-Defaults bleiben aktiv, wenn kein Environment-Key gesetzt ist. Ein Feld
ohne Default ist für ein aktiviertes Modul erforderlich. Environment-Strings werden
durch das owning schema in `int`, `bool`, URL und weitere deklarierte Typen
umgewandelt.

```env
OCP_MODULE_BIOTOPES_API_URL=https://example.org
OCP_MODULE_BIOTOPES_TIMEOUT_SECONDS=20
OCP_MODULE_BIOTOPES_API_TOKEN=
```

Nur aktivierte Module werden geladen und validiert. Ein deaktiviertes Modul verlangt
deshalb weder `API_TOKEN` noch andere Pflichtwerte. Bei einem aktiven Modul stoppt
ein fehlender oder ungültiger Wert den Bootstrap vor Modulinstanziierung, Lifecycle-
Hooks, Datenbankverbindungen oder externen Requests. Der Fehler nennt Modul,
Namespace, Feld und erwarteten Environment-Key, niemals den eingegebenen Wert.

## Zugriff im Modul

```python
def register(self, context: ModuleContext) -> None:
    assert context.settings is not None
    settings = context.settings.require(BiotopesSettings)
```

Der Adapter ist an genau ein Modul und einen Modelltyp gebunden. Er bietet keinen
Zugriff auf Host-Settings oder Konfiguration anderer Module. Benötigt ein Modul eine
fachliche Fähigkeit eines anderen Moduls, verwendet es dessen öffentlichen
[Service-Contract](service-contracts.md), nicht dessen Settings.

Der ältere Key-basierte `get()`-/`require()`-Zugriff bleibt während der jungen
SDK-Migration kompatibel, ist aber ebenfalls auf das eigene Modell begrenzt. Neuer
Modulcode verwendet den typisierten Modellzugriff. Module importieren nicht
`app.core.config.get_settings`; ein fokussierter AST-Test schützt diese Grenze.

Der Architecture-Check blockiert für neue Repository-Module außerdem direktes
`os.environ`/`os.getenv` und eigene dotenv-/`BaseSettings`-Loader. Das offizielle
Secret-Primitive bleibt der namespacete Settings-Port.

## Secrets

Secrets werden ausschließlich explizit mit Pydantic `SecretStr` oder `SecretBytes`
markiert. Feldnamen wie `TOKEN` oder `PASSWORD` allein gelten nicht als sichere
Klassifikation. Secret-Typen maskieren ihre Darstellung und dürfen nicht als public
markiert werden.

Diese Regeln vermeiden versehentliche Zugriffe und Datenabfluss, sind aber keine
Python-Sandbox. In-Process-Code besitzt faktisch die Rechte des Hostprozesses und
muss nach dem [Trust-Modell](../architecture/adr-module-trust-model.md) vollständig
vertrauenswürdig sein.

Die Registry protokolliert keine Konfigurationswerte, speichert keine Werte in
Metriklabels oder Trace-Attributen und übernimmt keine vollständigen Environment-
Dumps. Validierungsfehler werden auf sichere Kontextfelder reduziert. Rotation
erfolgt zunächst durch Environment-Update und Restart; Hot Reload, Vault, Remote
Config und automatische Rotation gehören nicht zu diesem Contract.

## Explizit öffentliche Frontend-Konfiguration

Alle Felder sind standardmäßig backend-private. Nur
`json_schema_extra={"public": True}` nimmt ein Feld in den maschinenlesbaren
Public-Export auf. Die Registry serialisiert ausschließlich dieses Subset in
JSON-kompatible Werte:

```json
{
  "biotopes": {
    "api_url": "https://example.org"
  }
}
```

`api_token` und nicht markierte Werte fehlen vollständig. `SecretStr`,
`SecretBytes` sowie Modelle, die darunter verschachtelte Secrets enthalten, werden
als public abgelehnt. #99 definiert damit den sicheren Exportmechanismus, aber noch
keine Frontend-Modulruntime und keinen neuen öffentlichen Endpoint. Werte werden
nicht automatisch nach Nuxt `runtimeConfig.public` oder `NUXT_PUBLIC_*` kopiert.

## Lebenszyklus

Der Bootstrap läuft in dieser Reihenfolge:

1. aktive Module entdecken und Manifeste validieren;
2. bestehende Dependency-Reihenfolge auflösen;
3. passive Settings-Contributions sammeln;
4. Environment einmal lesen und aktive Modelle validieren;
5. modulgebundene Contexts erzeugen;
6. Module registrieren und Registries versiegeln;
7. asynchrone Startup-Hooks ausführen.

Die `ModuleSettingsRegistry` ist runtime-skopiert und nach dem Bootstrap immutable.
Es gibt keinen globalen Secret Store und kein Nachladen pro Request.

## Deployment

Manuelle Ansible-Vault-Konfiguration kann `OCP_MODULE_…`-Zeilen direkt im
`stadtplaner_backend_env_content` führen. Im automatischen GitHub-Deploy bleibt
`STADTPLANER_BACKEND_ENV_CONFIG` die nicht-sensitive, vollständige
Host-Konfiguration. Modulwerte werden gesammelt im optionalen Environment Secret
`STADTPLANER_MODULE_ENV_CONFIG` gepflegt, weil dessen Schema mit den aktivierten
Modulen wächst und sowohl öffentliche als auch geheime Felder enthalten kann.

Der Builder akzeptiert dort ausschließlich `OCP_MODULE_`-Keys, lehnt ungültige oder
doppelte dotenv-Zeilen ab und schreibt das Ergebnis nur in die bestehende
restriktive, atomar aktivierte Backend-Environmentdatei. Inhalte werden nicht
geloggt. Es gibt keinen Shell-`echo`-Pfad und keine Umwandlung echter Zeilenumbrüche
in literale `\n`-Sequenzen.

## Audit der bestehenden Host-Settings

Bestehende Variablen bleiben zunächst kompatibel. Die grobe Ownership-Inventur
leitet spätere Fachmigrationen, ändert aber in #99 keine produktiven Namen:

| Kategorie | Beispiele | Behandlung |
| --- | --- | --- |
| Host/Core | `APP_ENVIRONMENT`, `DATABASE_URL`, CORS, Host-URLs, Request-Limits | bleibt zentral |
| Shared Infrastruktur | Redis, SMTP, OAuth/Auth, Observability, Map-Preview-Runtime | bleibt bis zu einem eigenen Plattformvertrag zentral |
| Fachsettings | Mastodon Publishing, AI Search, OSM/Overpass, Nominatim, Superset, fachliche Cache-TTLs | bei Migration des owning module namespacen |
| Secrets | JWT/OAuth/MFA, SMTP, Provider-Keys, Mastodon-Token | bestehende Secret-Verteilung bleibt; neue Module verwenden explizite Secret-Typen |
| Öffentlich frontend-relevant | Site-/API-URL, Kartenstil, Kartenstart, Kontaktangaben | bestehende `NUXT_PUBLIC_*`-Werte bleiben; Modulwerte nur per Opt-in-Export |
| Deployment-only | Release-SHA, Backup-, Pfad-, Port- und systemd-/Ansible-Werte | nicht in Fachschemas verschieben |
| Legacy | bestehende fachliche Felder in `Settings` und `get_settings()`-Consumer | schrittweise beim jeweiligen Pilot-Issue migrieren |

## Migrationsstrategie für Legacy-Variablen

1. Bestehende Variablen und `get_settings()` bleiben unverändert funktionsfähig.
2. Bei Migration einer Domäne erhält ihr Modul ein Schema und den neuen
   `OCP_MODULE_…`-Key.
3. Falls nötig liest ein zeitlich begrenzter Adapter zusätzlich den alten Key und
   dokumentiert Deprecation sowie Vorrang eindeutig.
4. Der Alias entfällt nur in einem angekündigten Major-/Kompatibilitätsfenster.

Beispielhafte Planung:

| Aktuelle Variable | Künftiger Owner | Künftige Variable | Zeitpunkt |
| --- | --- | --- | --- |
| `MASTODON_BASE_URL` | `social` | `OCP_MODULE_SOCIAL_MASTODON_BASE_URL` | Migration der Social-Domäne |
| `AI_SEARCH_PROVIDER` | `assistant` | `OCP_MODULE_ASSISTANT_SEARCH_PROVIDER` | Migration des Assistants |
| `NOMINATIM_BASE_URL` | `geocoding` | `OCP_MODULE_GEOCODING_BASE_URL` | Einführung des Geocoding-Moduls |
| `OVERPASS_API_URL` | `osm` | `OCP_MODULE_OSM_OVERPASS_API_URL` | OSM-Modulmigration |
| `FLENSBURG_SUPERSET_BASE_URL` | `statistics` | `OCP_MODULE_STATISTICS_SUPERSET_BASE_URL` | Pilot-/Statistikmigration |

Diese Tabelle ist eine Zielplanung, keine aktuelle Umbenennung oder Aktivierung.
