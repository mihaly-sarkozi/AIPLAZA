# Settings modul

Szerző: Sárközi Mihály  
Dátum: 2026-05-24  
Backend route: `/api/settings`, `/api/settings/sections`  
Frontend route: `/admin/settings`

## Mit csinál?

A `settings` app modul a tenant/felhasználói beállítások HTTP adaptere. Nem saját adatbázis-réteget tart fenn, hanem a core platform settings szolgáltatásra támaszkodik, és azt teszi elérhetővé app-modul szerződésen keresztül.

Fő funkciói:

- beállítások lekérése (`GET /api/settings`)
- beállítások módosítása (`PATCH /api/settings`)
- settings szekciók listázása (`GET /api/settings/sections`)
- frontend route regisztráció az `/admin/settings` oldalhoz
- settings jogosultságok deklarálása: `settings.read`, `settings.write`

## Mitől függ?

- `core.kernel.interface`: modulregisztráció, route registration, module context
- `core.kernel.http.app_dependencies`: runtime service lookup a FastAPI requestből
- `core.kernel.interface.keys.PLATFORM_SETTINGS_SERVICE`: core platform settings service kulcsa
- `core.modules.settings.registry.settings_section_registry`: settings szekciók listázása
- `core.modules.auth.web.dependencies.auth_dependencies.require_permission`: route jogosultság-ellenőrzés
- `core.modules.users.domain.dto.User`: az aktuális user típusa

## Fájlok

- `bootstrap/app_module.py`: a settings app modul runtime beüzemelése. Regisztrálja a `SettingsFacade` szolgáltatást, beköti az API routert, deklarálja a függőségeket és permissionöket.
- `bootstrap/service_keys.py`: a settings modul service kulcsát definiálja (`SETTINGS_SERVICE`), vagyis milyen néven érhető el a facade a runtime module service registryben.
- `bootstrap/dependencies.py`: FastAPI dependency adapterek. Innen jön a facade dependency és a `settings.read` / `settings.write` user dependency.
- `bootstrap/tenant_hooks.py`: settings tenant hook export adapter a core settings tenant hookhoz.
- `api/router.py`: HTTP route-ok. A requestet továbbadja a facade-nak, üzleti logikát nem tartalmaz.
- `api/SettingsUpdateRequest.py`: a `PATCH /api/settings` request Pydantic sémája.
- `api/SettingsSectionResponse.py`: a `GET /api/settings/sections` response elem Pydantic sémája.
- `service/settings_facade.py`: app-szintű orchestrator. A core settings service snapshotját domain állapottá alakítja.
- `domain/settings_state.py`: frameworkfüggetlen settings állapot és engedélyezett formátum literal típusok.
- `web/module.tsx`: frontend moduldefiníció az `/admin/settings` route-hoz és menüponthoz.
- `__init__.py`, `service/__init__.py`: csomagjelölő/export fájlok, jelenleg runtime logika nélkül.

## Fontos architekturális megjegyzés

Ez a modul app adapter, nem a platform settings domain tulajdonosa. A tényleges perzisztencia és core settings implementáció a `core.modules.settings` oldalon van. Emiatt a settings app modul feladata a vékony HTTP/API és module boundary fenntartása.
