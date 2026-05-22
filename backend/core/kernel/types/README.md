# core/kernel/types

A `types` könyvtár a kernel könnyű, runtime-független type alias rétege. Jelenleg a lifecycle hook callable típusokat tartalmazza, amelyeket a modul contract és az app manifest közösen használ.

## Fő felelősség

Ez a csomag csak típus/szerződés definíciókat ad. Nem épít runtime objektumot, nem olvas konfigurációt, nem köt be FastAPI-t és nem tartalmaz domain logikát.

## Fájlok

- `__init__.py`: lifecycle hook típusok exportja.
- `lifecycle_hook_types.py`: `LifecycleHook`, `TenantSchemaRegistrar` és `BootstrapHook` callable aliasok.

## Kapcsolódás a nagy egészhez

A `BaseAppModule` ezekkel a típusokkal írja le, milyen hookokat adhat vissza egy modul. Az `AppManifest` ugyanezeket gyűjti össze, majd az app bootstrap és lifespan réteg futtatja őket a megfelelő pillanatban.

# Sárközi Mihály - 2026.05.21
