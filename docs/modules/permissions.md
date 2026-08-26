# Modul-Permissions

Der Host besitzt die `PermissionRegistry` und die Auswertung, Fachmodule besitzen
ihre stabilen Permission-IDs. Eine Definition beschreibt, dass ein Recht existiert;
ein Grant beschreibt unabhängig davon, ob eine aktuelle Identity es erhält. Dieses
Modell ergänzt die bestehenden Rollen und ersetzt weder Authentifizierung, MFA,
CSRF noch die Datenbank durch ein neues RBAC-System.

## Definition und Bootstrap

Backend-Module deklarieren ihre Rechte einmalig im Feld `permissions` ihres
Manifest V1. Die Runtime registriert nur Manifeste aktivierter Module, sortiert die
Definitionen deterministisch und versiegelt die Registry nach `register()`. Danach
sind Mutationen ein Bootstrapfehler. Doppelte IDs, ungültige IDs und fremde
Namespaces schlagen fail-fast mit strukturierten Fehlern fehl.

IDs folgen `<module-id>.<permission-name>` in lowercase kebab-case, zum Beispiel
`statistics.import`. Ein Fachmodul darf nur `<eigene-id>.*` definieren;
`platform.*` ist echten Host-Rechten vorbehalten. IDs sind öffentliche, dauerhafte
Contracts. Eine Ablösung wird über `deprecated` und `replacement` dokumentiert,
nicht durch stilles Umbenennen. Historische Auditdatensätze speichern weiterhin die
alte lesbare String-ID, auch wenn das Modul später deaktiviert wird.

`PermissionDefinition` bietet zusätzlich Beschreibung, Kategorie und
Deprecation-Metadaten. Das Manifest bleibt die Existenzquelle, damit ID-Listen nicht
in Manifest und Runtimecode parallel gepflegt werden.

## Auswertung und Sicherheit

`PermissionEngine.allows(subject, permission_id)` wertet ausschließlich bekannte,
aktive Definitionen aus. Unbekannte IDs werden verweigert und strukturiert ohne
Policy- oder personenbezogene Details protokolliert. FastAPI-Routen verwenden
`require_permission(...)`; UI-Sichtbarkeit ersetzt niemals diese serverseitige
Prüfung.

Der temporäre `LegacyRolePermissionResolver` bildet bestehende Rollen auf IDs ab:

- Superuser erhalten als dokumentierter universeller Bypass alle registrierten
  Rechte, aber niemals unbekannte oder deaktivierte IDs.
- `VERWALTUNG` erhält derzeit `platform.verwaltung`.
- Normale Konten erhalten ohne explizites Mapping kein administratives Recht.

Der Pilot `social.publish` bleibt für Superuser reserviert. Seine Routen verwenden
weiterhin die bestehende starke MFA-Prüfung und bei Mutationen CSRF. Die fachliche
Definition liegt beim Social-Publishing-Adapter, nicht in einer wachsenden
Core-Liste.

## Frontend-Snapshot

Bestehende Current-User- und Session-Antworten enthalten additiv `permissions` als
sortierte Liste der tatsächlich gewährten, aktiven IDs. Sie enthalten keine
Resolverregeln oder sonstige neue Policy-Interna. Der Pinia-Auth-Store hält diesen
serverseitigen Snapshot; `hasPermission()` und die Visibility aus #102 lesen nur
diese Liste und verhalten sich bei fehlendem Zustand, unbekannten IDs und während
SSR/Hydration default-deny. Local Storage, Queryparameter und Header sind keine
Grant-Quelle.

Capabilities beantworten dagegen, ob ein Modul eine technische Fähigkeit anbietet,
nicht ob ein Benutzer handeln darf. Die vorhandenen Manifest-Capabilities bleiben
deshalb Discovery-Metadaten; #104 führt bewusst kein zweites Security-System ein.

## Migrationsmatrix

| Bisheriger Check | Owner | Ziel-ID | Stand |
|---|---|---|---|
| `is_superuser` für Social Publishing | Social | `social.publish` | Pilot migriert; MFA/CSRF unverändert |
| `is_superuser` für Rollen-/Benutzerverwaltung | Platform/Auth | `platform.superuser` | Definition/Snapshot vorhanden; Route später |
| Rolle `VERWALTUNG` für Kennzahlen | bisher Analytics | künftig fachliches `statistics.*` | vorerst kompatibel über `platform.verwaltung` |
| Polygon-Eigentümer/`VERWALTUNG` | Polygons | künftig `polygons.*` plus Resource Policy | später; keine Verhaltensänderung |
| Statistikimport-CLI | Statistics | künftig `statistics.import` | später; kein HTTP-Grant in #104 |

Rollout benötigt keine Datenbankmigration. Ein Rollback auf den vorherigen Release
entfernt das additive Snapshot-Feld und stellt die alten Social-Dependencies wieder
her; gespeicherte Daten und Auditlogs bleiben unverändert.
