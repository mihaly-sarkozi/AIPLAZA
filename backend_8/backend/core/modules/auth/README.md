# core/modules/auth

Az `auth` modul a tenant felhasználók autentikációs és belépési platform modulja. Kezeli a login, refresh, logout, 2FA, authenticator setup, JWT token, refresh session, token allowlist és auth middleware működést, valamint permission/role dependency helperöket ad a routereknek.

## Fő felelősség

A modul a felhasználói auth flow-k domain és application logikáját tartalmazza. A kernel adja hozzá a közös HTTP, security, DI, logging és DB infrastruktúrát, de a token kiadás, session rotation, 2FA challenge, logout és authorization dependency már az auth modul felelőssége.

## Rétegek

- `auth.py`: `AuthCoreModule`, amely összerakja és platform service kulcsokon regisztrálja az auth service-eket.
- `container/`: a login, refresh, logout és 2FA service-ek runtime feature bundle-je.
- `domain/`: DTO-k, ORM modellek, portok, password/2FA/authorization policy és auth exceptionök.
- `repository/`: tenant-séma repositoryk, token allowlist és permissions-changed store Redis/in-memory adapterrel.
- `use_cases/`: login, refresh, logout és 2FA application service-ek.
- `service/token_service.py`: JWT access, refresh, platform-admin és demo-login tokenek kezelése.
- `middleware/auth_middleware.py`: Bearer token validáció és request user feloldás.
- `router/`: auth HTTP API, request/response sémák, response builder és demo-login handler.
- `web/dependencies/`: FastAPI/WebSocket current user, permission és role dependency-k.
- `web/rate_limit/`: login rate limit policy és Redis/in-memory adapter.
- `tenant_hooks.py`: auth táblák tenant schema provisioning hookja.

## Kapcsolódás a nagy egészhez

Az `AppManifest` tölti be az `AuthCoreModule`-t. Az `AuthCoreModule` a settings és clock platform service-ekre épít, majd regisztrálja a `PLATFORM_LOGIN_SERVICE`, `PLATFORM_REFRESH_SERVICE`, `PLATFORM_LOGOUT_SERVICE`, `PLATFORM_AUTH_TWO_FACTOR_SERVICE` és `PLATFORM_AUTH_SESSION_REPOSITORY` függőségeket. A kernel HTTP middleware lánc az `AuthMiddleware`-t használja, a core route registry pedig az auth routert köti be `/api/auth/*` útvonalakra.

## Tenant és Security

Az auth adatok többsége tenant sémában él: refresh tokenek, 2FA kódok, 2FA próbálkozások, pending 2FA loginok és user authenticatorok. Az access token érvényességet a token allowlist szűri, production többpéldányos környezetben Redis szükséges. A refresh flow security version, permissions changed flag, session hash és fingerprint ellenőrzést is végez.

## Platform Jelleg

Ez core platform modul, nem kernel framework elem. Általános auth képességet ad minden tenant appnak, de konkrét AIPLAZA platform szabályokat is tartalmaz, például tenant security version, demo-login és platform-admin token típus támogatást. Ezért helye a `core/modules/auth`, nem a `core/kernel`.

## Sárközi Mihály - 2026.05.21