# Passkeys / WebAuthn

Stadtplaner verwendet Passkeys als bevorzugte moderne Authentifizierungsmethode. Die Implementierung basiert auf dem WebAuthn-Standard und der serverseitigen Python-Bibliothek `webauthn` von Duo Labs. Passkeys funktionieren sowohl passwortlos als auch als zweiter Faktor nach Passwort- oder OAuth-Anmeldung.

## Architektur und Sicherheitsinvarianten

- Die Relying-Party-Werte stammen ausschließlich aus `WEBAUTHN_RP_ID`, `WEBAUTHN_RP_NAME` und `WEBAUTHN_ORIGIN`. Untrusted Request-Header bestimmen weder Origin noch RP-ID.
- Registration, passwortloser Login und MFA-Step-up besitzen je eine kryptografisch zufällige, kurzlebige Challenge in `webauthn_challenges`. Ein separates zufälliges Ceremony-Token wird nur gehasht gespeichert. Verifikation sperrt die Challenge-Zeile und konsumiert sie einmalig.
- `webauthn` prüft Challenge, Origin, RP-ID-Hash, User Presence, User Verification und die kryptografische Signatur. Erst danach darf die bestehende `issue_session()`-Logik Access-, Refresh- und CSRF-Cookies ausstellen.
- Passkeys verwenden die stabile Benutzer-UUID als binären User Handle. Passwortloser Login ermittelt das Konto über die Credential-ID und gleicht einen gelieferten User Handle zusätzlich ab.
- `user_webauthn_credentials` speichert ausschließlich Credential-ID, COSE Public Key, Sign Counter und nicht geheime Metadaten. Private Schlüssel und biometrische Merkmale verbleiben auf Authenticator beziehungsweise Endgerät.
- Attestation ist `none`, um unnötiges Geräte-Fingerprinting zu vermeiden. Discoverable Credentials sind `preferred`; User Verification ist bei Registration und Authentication `required`.
- Ein Sign Counter von null ist gültig. Bei Regression wird der gespeicherte Zähler nicht abgesenkt und ein Audit-Ereignis geschrieben. Dies berücksichtigt synchronisierte Multi-Device-Passkeys, ohne Auffälligkeiten zu verschweigen.
- Credential-, Challenge-, Signatur-, ClientData-, Attestation- und Public-Key-Rohdaten werden weder in Audit-Metadaten noch in Anwendungslogs geschrieben.
- Authentifizierte Änderungen sind CSRF-geschützt. Entfernen eines Passkeys verlangt zusätzlich eine frische Passkey-Reauthentication; die letzte verbleibende Anmeldemethode kann nicht entfernt werden.

## Betrieb

Development:

```env
WEBAUTHN_RP_ID=localhost
WEBAUTHN_RP_NAME="Stadtplaner OK Lab Flensburg"
WEBAUTHN_ORIGIN=http://localhost:3000
WEBAUTHN_CHALLENGE_EXPIRE_SECONDS=300
WEBAUTHN_TIMEOUT_MS=60000
```

Production benötigt HTTPS. Beispiel:

```env
WEBAUTHN_RP_ID=stadtplaner.oklabflensburg.de
WEBAUTHN_RP_NAME="Stadtplaner OK Lab Flensburg"
WEBAUTHN_ORIGIN=https://stadtplaner.oklabflensburg.de
```

Nach Installation der Python-Abhängigkeiten `alembic upgrade head` ausführen. Migration `20260819_0027` legt `user_webauthn_credentials` und `webauthn_challenges` an. RP-ID und Origin müssen zur tatsächlich im Browser sichtbaren Frontend-Origin passen; eine separate API-Subdomain darf nicht versehentlich als WebAuthn-Origin konfiguriert werden.
