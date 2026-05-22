# scaffolding

A `scaffolding` könyvtár az új `backend/apps/*` app modulok induló sablonja. 

## Fő felelősség

A könyvtár olyan minimális app modult mutat, amely követi a platform modulkonvenciót: van backend `module.py`, service, router és frontend `web/module.tsx`. A `scripts/create_app_module.py` innen másolja a fájlokat az `apps/<module_name>` alá, közben a `template` névvariánsokat az új modul nevére cseréli.

## Fájlok

- `module.py`: `TemplateAppModule`, service regisztráció, router bekötés, permission és `get_module()` factory.
- `router.py`: minimális FastAPI router `module_service_dependency` használattal.
- `service.py`: minimális service osztály healthcheck metódussal.
- `web/module.tsx`: frontend module definition placeholder, a valódi appokkal azonos `web/module.tsx` konvenció szerint.

## Fontos Határ

A `web/` alkönyvtár szándékosan megmaradt, mert a valós app modulok frontend belépési pontja is `web/module.tsx`. Az extra `app_template/` szint viszont nem hordozott jelentést, ezért lett eltávolítva.

## Kapcsolódás

A `scripts/create_app_module.py` és az architektúra tesztek közvetlenül ezt a könyvtárat használják template gyökérként. Ha a valós app modulok kötelező struktúrája változik, ezt a sablont és a hozzá tartozó architektúra tesztet együtt kell frissíteni.

## Sárközi Mihály - 2026.05.21
