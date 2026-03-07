# Tesztek – funkciónkénti lefedettség

## Auth (`test_auth_login.py`)
- **Login**: üres/rossz body 422, invalid credentials 401, step1 → 2FA required, step2 → tokens + cookie, 5× rossz jelszó 401, rate limit (step2 too many attempts) 429
- **Refresh**: nincs cookie/header 401, invalid/revoked 401, success + cookie, X-Refresh-Token header, fingerprint mismatch → re_2fa_required, same fingerprint → success
- **Me**: 401 nélkül, 200 + user adat
- **Logout**: auth nélkül 200, success 200
- **Forgot password**: 200 (ok), üres email 422
- **Change password**: 401 nélkül, rossz jelenlegi 400, success 200
- **PATCH /auth/me**: 401, success (name, locale, theme)
- **GET /auth/default-settings**: 200, locale + theme
- **2FA**: step2 too many attempts 429, 5× rossz kód majd 6. 429

## Users CRUD (`test_user_crud.py`)
- **List**: success, with data, non-superuser 403
- **Get**: success, 404
- **Create**: success, duplicate email 400
- **Update**: success, owner is_active 400
- **Delete**: success, delete self 400
- **Resend invite**: success, active user 400, not found 400

## Regisztráció / set-password (`test_registration.py`)
- **Validate token**: invalid/missing 400, expired 410, valid 200
- **Set password**: invalid 400, expired 410, success

## Settings (`test_settings.py`)
- **GET/PATCH**: 401 auth nélkül, 403 nem owner, 200 success

## Chat (`test_chat.py`)
- **POST /chat**: 401 auth nélkül, 200 success (mock), üres question 422/200

## Knowledge base (`test_knowledge.py`)
- **GET /kb**: 401 auth nélkül, 403 nem admin, 200 lista (mock)
- **POST /kb**: 401 auth nélkül, 200 created (mock)
- Opcionális később: PUT, DELETE, train/text, train/file (401/403/success)

## Token service – unit (`test_token_service.py`)
- Verify: helyes/rossz issuer, audience, nbf jövőbeni, decode_ignore_exp

## DB séma (`test_db_schema.py`)
- public.tenants, tenant_configs, tenant_domains; demo séma, users, knowledge_bases tábla szerkezet

---

## Összefoglaló
- **Auth, Users, Registration, Settings, Chat, Knowledge (alap)** – HTTP tesztek mock service-ekkel.
- **Knowledge**: PUT/DELETE/train endpointok nincsenek még lefedve – igény szerint bővíthető.
- **Event channel** (async security/audit): nincs dedikált teszt; a meglévő auth tesztek továbbra is átmennek (proxy vagy szinkron).
- **Integrációs** (valódi DB + valódi service): jelenleg mockolt repo/service; teljes e2e külön projekt lehet.
