# Zwei-Faktor-Authentifizierung (Passkeys und TOTP)

Stadtplaner unterstützt Passkeys/WebAuthn als bevorzugte starke Methode und optionale TOTP-Zwei-Faktor-Authentifizierung nach RFC 6238 (SHA-1, sechs Stellen, 30 Sekunden, Zeitfenster ±1). Die Einrichtung befindet sich unter `/profil/sicherheit`; WebAuthn-Details stehen in [passkeys.md](passkeys.md).

## Sicherheitsinvarianten

- Ein korrektes Passwort oder eine erfolgreiche OAuth-Antwort erzeugt bei einem MFA-Konto noch keine Sitzung. Beide Wege erzeugen nur eine fünf Minuten gültige, serverseitig gehashte und einmalig nutzbare Challenge.
- Erst `POST /api/v1/auth/mfa/verify` konsumiert Challenge und Faktor atomar und verwendet anschließend die bestehende `issue_session()`-Logik.
- TOTP-Secrets werden ausschließlich mit dem serverseitigen Fernet-Schlüssel `MFA_ENCRYPTION_KEY` verschlüsselt gespeichert und nach der Einrichtung nicht erneut ausgeliefert.
- Wiederherstellungscodes besitzen hohe Zufallsentropie, werden nur einmal angezeigt und serverseitig ausschließlich als HMAC-SHA-256 gespeichert. Jede Verwendung sperrt die Datenbankzeile.
- Der zuletzt akzeptierte TOTP-Zeitschritt wird gespeichert. Eine Zeilensperre verhindert die parallele Wiederverwendung desselben OTPs.
- Eine Challenge wird nach fünf Fehlversuchen ungültig. Zusätzlich begrenzt der zentrale Rate-Limiter Verifikation nach IP und Challenge-Fingerprint.
- MFA-Änderungen verlangen eine frische, serverseitig über `auth_time` geprüfte Anmeldung. Deaktivierung und Code-Regeneration verlangen zusätzlich Passwort (sofern vorhanden) und TOTP/Recovery-Code.
- MFA-Deaktivierung widerruft alle Refresh-Sitzungen. Refresh-Rotation übernimmt nach abgeschlossenem Login `auth_time` und `amr`, ohne erneut nach TOTP zu fragen.
- Aktivierung und Recovery-Code-Regeneration widerrufen alle anderen Refresh-Familien; die gerade per Step-up bestätigte Browser-Sitzung bleibt gezielt erhalten.
- Mit `REQUIRE_MFA_FOR_SUPERUSERS=true` verweigern die zentralen Superuser-Abhängigkeiten Admin-Zugriff, solange weder Passkey noch aktive TOTP-Methode eingerichtet und als `webauthn`, `otp` oder `recovery` im aktuellen JWT nachgewiesen ist. Die Sicherheitseinrichtungsseite bleibt erreichbar; anschließend ist eine neue starke Anmeldung erforderlich.
- Secrets, OTPs, Recovery-Codes und Challenge-Tokens dürfen weder in Audit-Metadaten noch in Logs gelangen.

## Betrieb

Vor der Migration einen eigenen Schlüssel je Umgebung erzeugen:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Den Wert ausschließlich als `MFA_ENCRYPTION_KEY` im Backend-Environment setzen. Ein Verlust des Schlüssels macht eingerichtete TOTP-Secrets unlesbar; der Schlüssel gehört daher in das verschlüsselte Secret-Backup. Danach `python -m app.cli.module_migrations preflight` und anschließend `upgrade` ausführen und Backend sowie Frontend neu starten.

Die Tabellen `user_mfa_methods`, `user_mfa_recovery_codes` und `auth_mfa_challenges` werden über Migration `20260819_0026` angelegt. Offene abgelaufene Challenges können später durch einen periodischen Cleanup gelöscht werden; ihre Ablaufprüfung erfolgt unabhängig davon bei jeder Verwendung.
