# Multi-tenant auth backend – refaktor és hardening roadmap

Összefoglaló: 17 cél, státusz és breaking-change megjegyzések. Minden változtatás megőrzi a létező üzleti logikát és minimalizálja a breaking change-eket.

---

## 1. Refresh token csak HttpOnly cookie ✅

- **Státusz:** Kész. A refresh token nem szerepel a response body-ban; csak cookie-ban (Set-Cookie). X-Refresh-Token header nem fogadható.
- **Hol:** `TokenResp` (nincs refresh_token mező), auth_router (csak cookie), docs/Token_es_titkositas_policy.md.
- **Előny:** XSS nem lopja a refresh tokent; policy egységes.

---

## 2. Production: veszélyes scriptek tiltása ✅

- **Státusz:** Kész. `config/prod_guard.py`: `reject_if_production(script_name, reason)`. `scripts/reset_passwords.py` meghívja; APP_ENV=prod esetén kilép.
- **Előny:** Véletlen bulk jelszó reset prod környezetben nem fut le.
- **Opcionális:** seed_user.py-nál prod guard csak akkor, ha gyenge default jelszó (pl. "123") – jelenleg nincs.

---

## 3. Invite/set-password TTL 1–4 óra + resend ✅ (TTL), resend már létezik

- **Státusz:** TTL: config `invite_ttl_hours` (alap 4), user_service minden invite/forgot path ezt használja (1–24 óra clampl). Resend: `resend_invite` endpoint és UserService.resend_invite már megvan.
- **Hol:** config/base.py `invite_ttl_hours`, user_service `_invite_ttl_hours()`, create / resend_invite / forgot_password.
- **Előny:** Rövid életű linkek, kisebb ablak a visszaéléseknek.

---

## 4. Audit sanitization réteg ✅

- **Státusz:** Kész. `apps/audit/sanitization.py`: `sanitize_details(details)` – password/token/secret kulcsok → [REDACTED], email opcionálisan ***@domain. Az event channel worker audit log előtt meghívja.
- **Hol:** event_channel.py worker, audit.log hívás előtt sanitize_details(details).
- **Előny:** Érzékeny adat nem kerül audit logba; compliance, adatvédelem.

---

## 5. Light-path auth szűkítése ✅

- **Státusz:** Kész. Light path config + feature flag: `auth_light_paths` (config/base.py, .env AUTH_LIGHT_PATHS); alap: `/api/chat`; üres = kikapcsolva. Mérés: INFO log `auth_light_path` (path, user_id, correlation_id). docs/Auth_light_paths.md.
- **Hol:** auth_middleware.py (light_paths param), main.py (_light_paths), config/base.py.
- **Előny:** Érzékeny route-ok mindig teljes user load; light path monitorozható; szűkíthető/ki kapcsolható env-vel.

---

## 6. CSP / security headerek production ✅

- **Státusz:** Kész. SecurityHeadersMiddleware: productionben (APP_ENV=prod) szigorúbb CSP: default-src 'self'; frame-ancestors 'none'; script-src 'self'; object-src 'none'; base-uri 'self'.
- **Hol:** main.py SecurityHeadersMiddleware.
- **Előny:** Production-kompatibilis CSP; XSS/clickjacking védelem.

---

## 7. Központi 2FA policy (retry / lock) ✅

- **Státusz:** Kész. `apps/core/security/two_factor_policy.py`: get_2fa_max_attempts(), get_2fa_attempt_window_minutes(), get_2fa_code_expiry_minutes(). Config: two_fa_max_attempts, two_fa_attempt_window_minutes, two_fa_code_expiry_minutes. TwoFactorService a containerból ezeket kapja.
- **Előny:** Egy helyen lehet finomhangolni; retry/lock szabályok konzisztensek.

---

## 8. Hot-path timing + correlation ID 🔄 részben kész

- **Státusz:** CorrelationIdMiddleware és RequestTimingMiddleware már van; X-Response-Time-Ms. Részletes hot-path span-ek (auth, refresh, DB) opcionálisan bővíthetők (pl. strukturált log correlation_id-val, vagy OpenTelemetry).
- **Javaslat:** Ha kell: auth_middleware és refresh route logoljon timingot correlation_id-val (pl. _log.info("auth_lookup", extra={"correlation_id": ..., "ms": ...})).

---

## 9. Audit + email async ✅ (audit), 🔄 (email)

- **Státusz:** Audit: SecurityAuditEventChannel queue + worker már aszinkron. Email: jelenleg szinkron (pl. 2FA kód, set-password invite). Email queue/event channel külön feladat (pl. ugyanaz a queue, vagy külön email queue worker).
- **Javaslat:** Email küldést is queue-ba tenni (event type "email"), worker hívja az email_service-t; így a request nem vár az SMTP-re.

---

## 10. Refresh hot path + auth query optimalizáció ✅ részben

- **Státusz:** Light path (/api/chat) már csökkenti a user loadot. Refresh path: session + token verify + user_ver check + rotation; a user load a version check miatt kell. Optimalizáció: cache (már van user cache); refresh path-on ne legyen felesleges DB hívás (jelenleg user_for_ver kell a role-hoz és ver-hez).
- **Javaslat:** Ha szükséges: refresh path-on user cache használata version check-hez (csak ha nincs cache, akkor DB).

---

## 11. Állapot Redisre productionben 🔄

- **Státusz:** Rate limit, allowlist, permissions_changed, auth_limits már Redis-t használnak, ha REDIS_URL be van állítva. Cache (tenant, user) is Redis ha van URL. Productionben REDIS_URL kötelező beállítás (dokumentációnkban); in-memory fallback csak dev.
- **Javaslat:** Prod configban ellenőrizni: ha APP_ENV=prod és redis_url üres, warning vagy indítási hiba (opcionális).

---

## 12. Session policy: single-session / multi-device 🔄

- **Státusz:** Jelenleg multi-session (több refresh token / user lehet). Single-session: új login invalidálja a korábbi session(ök)et (pl. invalidate_all_for_user login előtt már van _issue_tokens-ban).
- **Javaslat:** Konfig: session_policy = "single" | "multi". Single: login时 invalidate_all_for_user (már közel van); refresh-nél csak az aktuális jti érvényes. Multi: jelenlegi viselkedés. Implementáció: session_repo.invalidate_all_for_user már hívódik _issue_tokens elején; single-session esetén ne engedjünk új refresh tokent addig, amíg a régi érvényes (vagy mindig invalidate_all előtt új session – már így van).

---

## 13. Migrációk PostgreSQL-kompatibilis + egységes rendszer 🔄

- **Státusz:** Scriptek (init_db, add_*_columns, create_2fa_tables, stb.) SQLAlchemy/raw SQL; PostgreSQL szintaxis. Egységes migrációs rendszer (pl. Alembic) nincs; verziózással ellátott migration mappát és egy „run all pending” scriptet érdemes bevezetni.
- **Javaslat:** Alembic init + migration mappa; meglévő scriptek átültetése migration step-ekre, vagy egy `scripts/migrate_all.py` ami verzió táblából olvas és futtatja a megfelelő SQL/scripteket sorrendben.

---

## 14. Egységes migrációs rendszer 🔄

- **Státusz:** Lásd 13. Egy verzió tábla (schema_version) + migration fájlok (timestamp_name.sql vagy .py) + egy runner.
- **Javaslat:** docs/MIGRATIONS.md + migration runner script; CI-ben migráció futtatás (opcionális).

---

## 15. Authorization policy (owner / admin / user) 🔄

- **Státusz:** get_current_user_admin (role in ("admin", "owner")) és route-szintű Depends már van. Központi „policy” modul: egy helyen definiált role → permission map (pl. owner: minden user CRUD + settings; admin: user CRUD; user: saját profil).
- **Javaslat:** apps/core/security/authorization.py: def can_edit_user(role, target_id, current_id), can_access_settings(role), stb.; a route-ok és user_service ezt hívják. Így a szabályok egy helyen vannak.

---

## 16. Központi input validáció (email / jelszó / publikus mezők) ✅

- **Státusz:** Kész. `apps/core/validation/`: email.py (is_valid_email, EMAIL_MAX_LEN), password.py (validate_password_strength, PASSWORD_MIN_LEN, PASSWORD_MAX_LEN). A route-ok és service-ek importálhatják; Pydantic validátorok is hivatkozhatnak rájuk.
- **Előny:** Egységes szabályok; jelszó erősség és email formátum egy helyen.
- **Következő lépés:** Beépíteni a set-password és change-password request validátorokba (ha még nem használják).

---

## 17. CI security guardok + production readiness checklist ✅ (dokumentum)

- **Státusz:** Ez a dokumentum (REFACTOR_ROADMAP.md) és a Token_es_titkositas_policy.md, Cookie_es_session_policy.md részben checklist. Dedikált CI guard: pytest, security header tesztek, prod_guard futtatása (pl. APP_ENV=prod python -c "from config.prod_guard import reject_if_production; reject_if_production('test')" → exit 1).
- **Javaslat:** docs/PRODUCTION_READINESS.md: checklist (Redis prodban, JWT_SECRET erős, CSP be, audit sanitization, 2FA policy, invite TTL, stb.). CI: pytest + optional bandit/safety run.

---

## Összefoglaló táblázat

| # | Cél | Státusz | Megjegyzés |
|---|-----|---------|------------|
| 1 | Refresh token csak cookie | ✅ | Body + header eltávolítva |
| 2 | Prod: veszélyes scriptek tiltása | ✅ | prod_guard + reset_passwords |
| 3 | Invite TTL 1–4h + resend | ✅ | invite_ttl_hours, resend már volt |
| 4 | Audit sanitization | ✅ | sanitization.py + event channel |
| 5 | Light-path szűk | ✅ | Csak /api/chat |
| 6 | CSP/security headerek prod | ✅ | Szigorúbb CSP ha prod |
| 7 | 2FA policy réteg | ✅ | two_factor_policy + config |
| 8 | Hot-path timing + correlation ID | 🔄 | Middleware kész; részletes span opcionális |
| 9 | Audit + email async | ✅ audit, 🔄 email | Email queue később |
| 10 | Refresh + auth optimalizáció | 🔄 | Light path + cache már van |
| 11 | Állapot Redis prod | 🔄 | REDIS_URL doc; optional startup check |
| 12 | Session policy single/multi | 🔄 | Multi most; single opció doc |
| 13 | Migrációk PG + egységes | 🔄 | Alembic / migrate runner javaslat |
| 14 | Egységes migrációs rendszer | 🔄 | Lásd 13 |
| 15 | Authorization policy | 🔄 | can_* függvények központi modulban |
| 16 | Központi input validáció | ✅ | validation/ email + password |
| 17 | CI guardok + prod checklist | ✅ doc | PRODUCTION_READINESS.md javaslat |

**Jelmagyarázat:** ✅ Kész, 🔄 Részben kész vagy javaslat dokumentálva.
