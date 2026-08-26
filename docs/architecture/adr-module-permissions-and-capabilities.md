# ADR: Modulbasierte Permissions und Capabilities

- Status: Angenommen
- Datum: 2026-08-26
- Entscheidung: Issue #104
- Epic: Issue #91

## Kontext und Entscheidung

Fachrechte dürfen nicht als wachsende Liste im Host entstehen. Der Host stellt eine
generische, beim Bootstrap versiegelte Permission-Registry und eine fail-closed
Policy-Auswertung bereit. Aktive Module deklarieren ihre IDs in ihrem Manifest;
Legacy-Fachbereiche liefern bis zu ihrer Modulmigration eng begrenzte Definitionen
aus ihrem eigenen Contract. Der Host besitzt nur echte `platform.*`-Definitionen.

Definition und Grant bleiben getrennt. Bestehende Rollen werden vorerst durch einen
Adapter ausgewertet; es entsteht keine zweite Rollen-Datenbank. Superuser behalten
den universellen Bypass für alle registrierten IDs. Unbekannte und durch
Deaktivierung entfernte IDs werden auch für Superuser verweigert.

Das Frontend erhält ausschließlich einen Grantsnapshot im Current-User-Contract.
Die Visibility-Registry aus #102 und fachliche Seiten-Middleware lesen denselben
Snapshot default-deny. Autoritative Entscheidungen verbleiben in FastAPI.

Capabilities sind keine Grants. Sie beschreiben vorhandene technische
Modulfähigkeiten und bleiben im bestehenden Manifest-/ModuleRegistry-Vertrag. Eine
separate Capability-Policy würde Begriffe verdoppeln und wird daher nicht eingeführt.

## Folgen

- IDs sind langlebige öffentliche Contracts und werden namespaced, deterministisch
  und duplicate-sicher registriert.
- Die Registry enthält nur Permissions aktivierter Module; historische String-IDs
  in Auditdaten bleiben unabhängig davon lesbar.
- Das additive SDK erhöht sich von 1.5.0 auf 1.6.0.
- `social.publish` ist der erste migrierte Fachcheck; starke MFA- und CSRF-Regeln
  bleiben orthogonal erhalten.
- Weitere Fachrechte werden schrittweise nach der Matrix in
  [Modul-Permissions](../modules/permissions.md) migriert.
