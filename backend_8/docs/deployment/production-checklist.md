# Production Checklist

## Minimalis env

Kritikus alapok:

- `APP_ENV=production`
- `JWT_SECRET`: legalabb 64 karakter, eros random.
- `JWT_ISSUER`
- `JWT_AUDIENCE`
- `DATABASE_URL`
- `REDIS_URL`
- `OBJECT_STORAGE_ENDPOINT`
- `OBJECT_STORAGE_BUCKET`
- `OBJECT_STORAGE_ACCESS_KEY_ID`
- `OBJECT_STORAGE_SECRET_ACCESS_KEY`
- `TRUSTED_HOSTS`
- `CORS_ORIGINS`
- `TENANT_BASE_DOMAIN`
- `INSTALL_HOST`

## Security guardok

Startupkor a security guardoknak fail-closed modon kell mukodniuk.

- Production Redis nelkul ne induljon, mert rate limit, replay vedelem es token allowlist megosztott state-et igenyel.
- Gyenge JWT secret tiltott.
- Production CORS/Trusted Hosts ne legyen tul tag.
- Cookie secure policy legyen production-kompatibilis.
- URL ingest izolalt worker nelkul ne legyen bekapcsolva.
- Legacy ingest route nincs engedelyezve.
- Runtime DDL tiltott app/repository kodban.

## Internal es admin endpointok

- `/internal/*` endpointokhoz `require_internal_admin()` kotelezo.
- Vedelmi modok:
  - service token (`X-Metrics-Token` vagy Bearer token);
  - production IP allowlist;
  - audit log;
  - rate limit.
- Jogosulatlan request 404-et kapjon, ne endpoint reszletet.

## Worker deploy

Legalabb ket process profil:

- web/API: `INSTANCE_ROLE=web`
- worker: `INSTANCE_ROLE=worker`

Knowledge ingest es index build hosszu jobok worker oldalon fussanak. URL ingest workerhez kulon egress policy kell.

## Readiness

`/readyz` akkor legyen zold, ha a szolgaltatas forgalmat kaphat.

Ellenorzott komponensek:

- DB;
- Redis deployed env-ben;
- object storage deployed env-ben;
- migrations;
- URL ingest isolation guard;
- outbox;
- SMTP, ha email feature aktiv;
- background worker status.

Productionben degraded kritikus hiba eseten nem-200 valasz.

## CI es release gate

Kotelezo ellenorzesek:

```bash
make lint
make typecheck
make test-unit
make check-no-runtime-ddl
make check-import-boundaries
make package
```

GitHub Actions workflow:

- `.github/workflows/ci.yml`
- push es pull_request esemenyre fut.

## Csomagolas

Tiszta backend zip:

```bash
make package
```

A package script kizart elemei:

- `__MACOSX`
- `.DS_Store`
- `._*`
- `__pycache__`
- `.pyc`, `.pyo`
- `.git`
- `.venv`, `venv`, `env`
- `node_modules`

## Go-live elotti gyors ellenorzes

- `/livez` 200.
- `/readyz` productionben 200.
- `/metrics` csak token/IP mellett elerheto.
- `/internal/health/outbox` jogosulatlanul 404.
- Audit log irhato.
- Outbox worker heartbeat friss.
- URL ingest private IP teszt blokkolt.
