# Profile modul

Szerző: Sárközi Mihály  
Dátum: 2026-05-24  
Backend route: `/api/profile`, `/api/profile/preferences`, `/api/auth/me`  
Frontend route: `/profile`, `/change-password`

## Mit csinál?

A `profile` app modul a bejelentkezett felhasználó profil- és preferenciafelületének app adaptere. A személyes profiladatok módosítását a core user/profile szolgáltatásra bízza, miközben az app-specifikus felületi preferenciákat tenant sémában tárolja.

Fő funkciói:

- aktuális profil lekérése (`GET /api/profile`)
- profiladatok módosítása (`PATCH /api/profile`)
- felületi preferenciák lekérése és módosítása (`GET/PATCH /api/profile/preferences`)
- profile tenant tábla létrehozása (`profile_preferences`)
- frontend route regisztráció a profil és jelszóoldalakhoz

## Mitől függ?

- `core.kernel.interface`: app modul regisztráció, route registration, module context
- `core.kernel.http.app_dependencies`: runtime service lookup a FastAPI requestből
- `core.kernel.interface.keys.PLATFORM_USERS_PROFILE_SERVICE`: core profil service
- `core.kernel.interface.keys.PLATFORM_TENANT_USAGE_SERVICE`: training státusz olvasása a profil payloadhoz
- `core.modules.auth.web.dependencies.auth_dependencies.get_current_user`: aktuális user dependency
- `core.kernel.http.tenant_dependencies.RequiredTenantContextDep`: tenant kontextus
- `core.modules.tenant.service`: tenant séma hook regisztráció és schema statement futtatás

## Fájlok

- `bootstrap/app_module.py`: a profile app modul runtime beüzemelése. Regisztrálja a facade-ot, routert, tenant hookot és platform service függőségeket.
- `bootstrap/service_keys.py`: a profile modul service kulcsát definiálja (`PROFILE_SERVICE`), vagyis milyen néven érhető el a facade a module service registryben.
- `bootstrap/dependencies.py`: FastAPI dependency adapterek. Innen jön a facade, aktuális user és tenant dependency.
- `bootstrap/tenant_hooks.py`: tenant schema hook, amely létrehozza a `profile_preferences` táblát.
- `api/router.py`: HTTP route-ok. A requestet a facade-nak adja tovább, üzleti logikát nem tartalmaz.
- `api/schemas.py`: profile és preference request/response Pydantic sémák.
- `domain/preferences.py`: frameworkfüggetlen profile preference domain modell.
- `infra/preferences_repository.py`: tenant sémás `profile_preferences` tábla repository.
- `mappers/profile_mapper.py`: core profil payload és app preference válasz payload összefűzése.
- `service/profile_facade.py`: app-szintű orchestrator a core profil service és preference service között.
- `service/preferences_service.py`: profile preference domain service, mezővalidációval és repository delegálással.
- `service/ports.py`: protokollok a facade/service tesztelhető függőségeihez.
- `web/module.tsx`: frontend moduldefiníció a profile és change-password route-okhoz.
- `__init__.py`, almappa `__init__.py` fájlok: csomagjelölő/export fájlok, runtime logika nélkül.

## Fontos architekturális megjegyzés

A profile app modul nem tulajdonolja a core user profilt. A név, nyelv, téma és auth-közeli profiladatok forrása a core user/profile service. Az app modul csak a HTTP/module boundaryt, a tenant preference táblát és a frontend route regisztrációt tartja egyben.
