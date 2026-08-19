# Security Policy

## Supported versions

Security fixes are applied to the current `main` branch. There are currently no separately maintained release branches.

## Reporting a vulnerability

Please do not publish vulnerabilities in a public issue. Use the [Stadtplaner contact page](https://stadtplaner.oklabflensburg.de/kontakt) and initially include only the technical details needed to reproduce and assess the issue. Allow the maintainers reasonable time to investigate and deploy a fix before disclosure. Do not access or retain data belonging to other people while researching an issue.

## Security architecture

- Access and refresh tokens are held in `HttpOnly` cookies. Short-lived access JWTs are bound to an issuer, audience and fixed algorithm. Refresh tokens rotate and server-side session families detect reuse.
- Cookie-authenticated mutations use double-submit CSRF protection. Refresh additionally requires an exact allowed `Origin` or `Referer` in production.
- Password and OAuth logins stop at a short-lived, one-time server-side MFA challenge when a strong factor is configured. OAuth MFA challenges use a narrowly scoped `HttpOnly` cookie and never appear in redirect URLs.
- TOTP secrets are encrypted; recovery codes use a dedicated HMAC pepper; OAuth state uses its own key. Passkeys store only public-key material.
- Superuser endpoints require a strong current authentication method (`otp`, `recovery`, or `webauthn`) in production. Admin mutations additionally require CSRF.
- Public GIS writes require an active, verified account. Ownership and management-role checks remain server-side.
- Redis provides atomic, cross-worker security rate limits in production. Expensive public queries are rate-limited, cached and receive a transaction-local PostgreSQL statement timeout.
- Request bodies, passwords, GeoJSON vertices, descriptions and serialized properties are bounded. Avatar files continue through the validated image re-encoding pipeline.
- Private/auth/admin responses are marked non-cacheable. Application and Nuxt responses add CSP, anti-framing, referrer, MIME-sniffing and cross-origin policies; production enables HSTS.

## Secrets and rotation

Production must use independent random values for `JWT_SECRET_KEY`, `OAUTH_STATE_SECRET`, `MFA_RECOVERY_PEPPER`, and `MFA_ENCRYPTION_KEY`. Never commit them or log tokens, OAuth codes, passwords, MFA values, recovery codes, CSRF values, or provider credentials.

Rotating `JWT_SECRET_KEY` invalidates active browser tokens. Rotating `MFA_RECOVERY_PEPPER` invalidates existing recovery codes; coordinate the rotation and require affected users to generate a new set. Losing `MFA_ENCRYPTION_KEY` makes existing TOTP registrations unusable, so include it in encrypted secret backups.

## Rate limiting and enumeration

Production deliberately fails closed when Redis security rate limiting is unavailable. Login and password-reset responses avoid account disclosure. Signup retains the existing `EMAIL_ALREADY_REGISTERED` response for product compatibility; this is an accepted enumeration risk mitigated by strict IP plus normalized-email rate limits. Revisit that contract if compatibility no longer requires it.

## Deployment requirements

Run the [production security checklist](docs/security/production-checklist.md) for every environment and release. The API, frontend, PostgreSQL and Redis must be deployed on trusted networks with TLS at the public edge. Run migrations before starting the updated application.
