# SECURITY P0 Runbook

Ez a dokumentum a P0 szintű teendőket írja le:

1. Secret rotáció (DB/JWT/SMTP)
2. Deploy előtti automata security gate
3. HTTPS/HSTS enforce reverse proxy szinten

## P1 kiterjesztés (adatvédelmi keményítés)

- PII mezők titkosítása app-szinten (`kb_personal_data.extracted_value`)
- Retention/TTL (`created_at`, `expires_at`)
- Lejárt PII purge script
- PII hozzáférés/törlés audit események

## 1) Secret rotáció

### 1.1 JWT rotáció

```bash
make rotate-jwt
```

Ez frissíti a `.env` fájlban a `JWT_SECRET` értékét.

### 1.2 DB jelszó rotáció

Ha a `.env` tartalmaz `DATABASE_URL`-t felhasználó + jelszó formában:

```bash
python3 scripts/rotate_secrets.py --env-file .env --rotate-db-url-password --apply-db-password
```

- `--apply-db-password` megpróbál `ALTER ROLE`-t futtatni PostgreSQL-ben.
- Ha nincs jogosultság, futtasd DBA jogosultsággal kézzel.

### 1.3 SMTP jelszó frissítés

Az új app password-öt kézzel add meg:

```bash
python3 scripts/rotate_secrets.py --env-file .env --set-smtp-password "<UJ_SMTP_PASSWORD>"
```

> Fontos: a Gmail app password rotációt Google oldalon kell elvégezni, ezt a script nem tudja automatikusan.

## 2) Deploy előtti automata security gate

```bash
make security-predeploy
```

A script ellenőrzi többek között:

- kötelező env változók megléte (`DATABASE_URL`, `JWT_SECRET`, `SMTP_PASSWORD`, `FRONTEND_BASE_URL`, `TRUSTED_HOSTS`, `CORS_ORIGINS`)
- JWT erősség
- CORS wildcard tiltás
- proxy configban HTTPS redirect + HSTS meglét

Production ellenőrzéshez (APP_ENV=prod követelménnyel):

```bash
python3 scripts/predeploy_security_check.py --env-file .env --proxy-config deploy/nginx/aiplaza.conf.example
```

## 3) HTTPS/HSTS reverse proxy

Kiinduló minta:

- `deploy/nginx/aiplaza.conf.example`

Kötelező elemek:

- HTTP -> HTTPS redirect (301/308)
- `Strict-Transport-Security` fejléc legalább `max-age=31536000`
- TLS 1.2/1.3

## 4) P1 parancsok

### 4.1 Sémabővítés + legacy PII titkosítás

```bash
make pii-harden
```

### 4.2 Lejárt PII rekordok törlése (cronból naponta)

```bash
make pii-purge
```

Javaslat: napi egyszer futtasd időzítve (cron/systemd timer/K8s CronJob).

