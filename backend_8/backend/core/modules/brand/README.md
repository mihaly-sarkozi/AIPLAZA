# core/modules/brand

A `brand` modul tenantonkénti platform branding beállításokat kezel. A modul lehetővé teszi a display név, logo URL, elsődleges szín, support email és public_enabled állapot olvasását és módosítását a `/api/platform/brand` HTTP felületen.

## Fő felelősség

A modul egy egyszerű tenant-séma beállítási táblát kezel, amelyből a platform UI vagy nyilvános felület brand adatokat olvashat. Az olvasás `brand.read`, a módosítás `brand.write` permissionhöz kötött, update esetén pedig audit esemény készül.

## Rétegek

- `brand.py`: `BrandCoreModule`, amely regisztrálja a repositoryt, service-t, routert, tenant hookot és permissionöket.
- `tenant_hooks.py`: tenant schema provisioning a `brand_settings` táblához.
- `domain/brand_settings_orm.py`: tenant-séma ORM modell a brand beállításokhoz.
- `domain/brand_policy.py`: default értékek, update normalizálás és response mapping.
- `repository/brand_repository.py`: brand settings olvasás és upsert adatbázis műveletek.
- `service/brand_service.py`: brand olvasás/frissítés application service, audit logolással.
- `router/brand_router.py`: FastAPI endpointok tenant contexttel és permission ellenőrzéssel.
- `web/requests/brand_update_request.py`: update request schema.
- `web/responses/brand_response.py`: brand response schema.

## Kapcsolódás a nagy egészhez

Az `AppManifest` tölti be a `BrandCoreModule`-t. A modul `PLATFORM_BRAND_REPOSITORY` és `PLATFORM_BRAND_SERVICE` kulcsokon publikálja a komponenseit, majd a router a kernel dependency façade-on keresztül kéri le a service-t. A tenant provisioning futtatja a `tenant_hooks.py` hookját új vagy frissített tenant sémákhoz.

## Sárközi Mihály - 2026.05.21