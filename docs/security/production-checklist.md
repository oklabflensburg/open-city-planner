# Production security checklist

## Required application settings

- [ ] `APP_ENVIRONMENT=production`
- [ ] `AUTH_COOKIE_SECURE=true` and an appropriate cookie domain/path
- [ ] `REQUIRE_MFA_FOR_SUPERUSERS=true`
- [ ] `REFRESH_REQUIRE_ORIGIN=true`
- [ ] `AUTH_RATE_LIMIT_BACKEND=redis`
- [ ] `RATE_LIMIT_FAIL_CLOSED=true`
- [ ] `REDIS_ENABLED=true` and Redis is reachable before traffic is enabled
- [ ] `JWT_ALGORITHM=HS256`, with the expected `JWT_ISSUER` and `JWT_AUDIENCE`
- [ ] Independent, randomly generated `JWT_SECRET_KEY`, `OAUTH_STATE_SECRET`, `MFA_RECOVERY_PEPPER`, and `MFA_ENCRYPTION_KEY` are injected from the secret store
- [ ] `CORS_ORIGINS`, `APP_BASE_URL`, `API_BASE_URL`, OAuth callbacks, `WEBAUTHN_ORIGIN`, and `WEBAUTHN_RP_ID` exactly match public deployment origins
- [ ] `TRUSTED_PROXIES` contains only the actual reverse-proxy addresses/CIDRs; otherwise leave it empty

The backend intentionally refuses to start when core production invariants are missing. Do not replace production values with the documented development defaults.

## Edge and network

- [ ] HTTPS-only redirects are active and HSTS is returned after HTTPS is confirmed everywhere
- [ ] CSP and the remaining security headers are preserved by the proxy/CDN
- [ ] PostgreSQL and Redis are not publicly reachable and require authenticated, encrypted connections where the platform supports them
- [ ] The application database role uses least privilege; migration credentials are separated when practical
- [ ] API and worker processes run as unprivileged users
- [ ] Firewall and egress policy allow only required OAuth, mail, map/data and Mastodon destinations

Example Nginx body and header baseline (adapt host-specific origins before use):

```nginx
client_max_body_size 6m;
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-Frame-Options "DENY" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
```

The application still enforces its own streamed-body limits when `Content-Length` is absent or false. Keep the proxy limit slightly above the configured avatar size plus multipart overhead, and never use it as the only control.

## Data and operations

- [ ] Run `alembic upgrade head` before the new backend starts; migration `20260819_0028` adds reset-token invalidation state
- [ ] Verify Redis persistence/eviction policy is suitable for security counters and that the configured prefix is environment-specific
- [ ] Automated encrypted database and secret backups exist, restore tests are scheduled, and retention is documented
- [ ] Logs are access-controlled, rotated and redacted; tokens, passwords, MFA values, OAuth codes and authorization headers never enter logs
- [ ] Monitoring alerts on authentication spikes, rate-limit backend failures, refresh reuse, repeated MFA failures and elevated database timeouts
- [ ] Dependency audits, security tests and application tests run in CI; critical advisories block deployment
- [ ] OS, Python, Node, database, Redis, proxy and container updates follow a defined patch cadence

## Release verification

- [ ] Backend tests and Ruff pass
- [ ] Frontend tests, typecheck and production build pass
- [ ] Existing Playwright tests pass against an isolated environment
- [ ] `pnpm audit --prod` and a Python dependency audit have been reviewed
- [ ] Login, OAuth+MFA, password reset, password-change logout, refresh rotation, admin MFA and verified GIS writes were smoke-tested
- [ ] Security headers were checked on the actual public frontend and API responses
