# backend/admin

A `backend/admin` könyvtár a platform-admin backend önálló területe. Nem része a `core/kernel` általános framework rétegének, és nem tenant/app feature az `apps` alatt; a teljes AIPLAZA platform üzemeltetéséhez tartozó admin login, MFA, admin user kezelés, tenant statisztika, security monitoring, alert kezelés és IP tiltás funkciókat fogja össze.

## Fő felelősség

Az admin terület külön platform-admin user tárolót és refresh session kezelést használ a public schema alatt. A HTTP felület a `/api/platform-admin` prefix alatt érhető el, rate limittel, audit loggal, CSRF védelemmel, platform-admin cookie policyvel és opcionális IP allowlisttel.

## Fájlok

- `admin.py`: `AdminCoreModule`, service regisztráció, router bekötés és első admin bootstrap hook.
- `__init__.py`: lazy export az `AdminCoreModule` felé.
- `domain/admin_models.py`: platform-admin ORM modellek user, invite, refresh token, MFA attempt, security alert és IP ban táblákhoz.
- `domain/event_catalog.py`: security monitoring eseménykatalógus és kategóriák.
- `repository/platform_admin_repository.py`: admin perzisztencia, tenant statisztikák, security monitoring, alert és IP ban adatlekérdezés.
- `repository/schema_migrations.py`: legacy `platform_security_alerts` séma kompatibilitási helper.
- `service/platform_admin_service.py`: admin login, refresh, MFA, user management, monitoring és alert üzleti műveletek.
- `router/admin_router.py`: FastAPI HTTP adapter a `/api/platform-admin` endpointokhoz.
- `web/schemas/platform_admin_schemas.py`: Pydantic request/response modellek.

## Kapcsolódás a nagy egészhez

Az `AppManifest` továbbra is betölti az `AdminCoreModule`-t, de már az `admin.admin` importútvonalról. A modul a `PLATFORM_ADMIN_SERVICE` kulcson publikálja a `PlatformAdminService` példányt, a router pedig ezt a kernel dependency façade-on keresztül kéri le. Startupkor opcionálisan létrehozza az első admin felhasználót a megfelelő `.env` beállítások alapján.

## Határok

Tenant user adminisztráció, tenant belső permission kezelés vagy üzleti app admin funkció ne ide kerüljön. Ide azok a funkciók tartoznak, amelyek a platform egészét érintik: üzemeltetői belépés, platform szintű monitoring, biztonsági riasztás, IP tiltás és globális tenant áttekintés.

## Sárközi Mihály - 2026.05.21
