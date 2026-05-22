# core/kernel/config

## Feladat
A `config` könyvtár az alkalmazás központi konfigurációs rétege. Itt van a settings modell, az env betöltés public API-ja, valamint a settings mezők validációs és konstans helper rétege.

## Public API
- `config_loader.settings`: Lazy settings proxy; az első attribútum-eléréskor hozza létre a cache-elt AppSettings példányt.
- `config_loader.get_settings()`: Explicit settings lekérés.
- `config_loader.get_app_env()`: Az APP_ENV validált értéke.
- `bootstrap_guards.validate_settings()`: Környezetfüggő config/bootstrap szerződés ellenőrzése startupkor.
- `AppSettings` / `BaseConfig`: A teljes backend által használt settings szerződés.

## Fájlok
- `environment.py`: APP_ENV normalizálás és környezet helper API. Kanonikus értékek: `local`, `test`, `staging`, `production`; a régi `dev` -> `local`, `prod` -> `production` kompatibilis alias.
- `config_loader.py`: Opcionálisan betölti a `.env` és `.env.local` fájlokat, validálja az APP_ENV-et, de importkor nem dob `.env` hiány miatt. `get_settings()` nem futtat deployment guardot.
- `bootstrap_guards.py`: Startup/bootstrap guard a config betöltési szerződéshez: `local` alatt `.env` ajánlott/opcionális, `test` env varokból is működhet, `staging` és `production` alatt explicit env varok kötelezők.
- `base.py`: A központi Pydantic settings modell meződefiníciói és model validator bekötései.
- `settings_constants.py`: Közös config konstansok, regexek és megengedett értékkészletek.
- `settings_validators.py`: Kompatibilis facade, amely re-exportálja a szétbontott validator modulokat.
- `settings_basic_validators.py`: Jelszó policy, cookie, token TTL és 2FA alapszintű validációk.
- `settings_infra_validators.py`: Upload, observability és embedding beállítások validációja.
- `settings_limit_validators.py`: Rate limit, quota, chat, websocket, outbox és demo signup limitek validációja.
- `settings_production_validators.py`: Production hardening: JWT, HTTPS/CORS, trusted hosts, SMTP, database, Redis és debug bypass tiltások. A nem-local (`dev/test/staging/prod`) JWT_SECRET env-követelményt startup guard is érvényesíti.
- CSP lazítás csak célzott settings mezőkkel történjen (`security_csp_extra_connect_src`, `security_csp_extra_img_src`, `security_csp_extra_frame_src`), ne kódban vagy wildcarddal.
- `__init__.py`: Rövid lazy importfelület a `settings` eléréséhez.

## Kapcsolódás
A `backend/main.py`, az app factory, bootstrap builderek, runtime wiring, HTTP middleware-ek, core modulok és app modulok a `config_loader.settings` vagy `get_settings()` API-n keresztül olvassák a konfigurációt. Importkor nincs végzetes `.env` döntés; a startup guardokat a `security_startup_checks.py` futtatja `validate_settings()` belépési ponton keresztül.

## Deployment Szerződés

- `local`: in-memory fallback megengedett, `.env` opcionális/ajánlott.
- `test`: fake/in-memory provider megengedett, `.env` nélkül env varokból is futhat.
- `staging`: Redis, object storage és secure cookie kötelező; veszélyes fallbackek nem használhatók.
- `production`: minden staging követelmény érvényes, plusz éles security guardok tiltják a debug/bypass/legacy kapcsolókat.

Readiness endpointok:
- `/livez`: csak azt jelzi, hogy a process él.
- `/readyz`: DB, Redis, object storage, outbox worker státusz és public migration állapot alapján ad `ready` vagy `not_ready` választ.

## Fontos elv
A `base.py` maradjon a meződefiníciók helye. A hosszabb validációs logika külön `settings_*_validators.py` modulokba tartozik, hogy a settings modell olvasható és áttekinthető maradjon.

## Sárközi Mihály - 2026.05.21
