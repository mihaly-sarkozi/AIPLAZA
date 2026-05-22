# core/kernel/interface

Az `interface` könyvtár a kernel stabil, publikus szerződésrétege. Ide kerülnek azok a könnyen importálható típusok, kulcsok és konvenciók, amelyeket app modulok, core modulok és architektúra tesztek közösen használhatnak anélkül, hogy runtime assembly vagy infrastruktúra részletekhez kötnének.

## Fő felelősség

Ez a csomag a platform boundary-t írja le. A modulok innen kapják a `BaseAppModule`, `ModuleContext`, `RouteRegistration`, `platform.*` és `module.*` service kulcsokat, valamint az importszabályok géppel ellenőrizhető listáit.

## Fájlok

- `__init__.py`: stabil public export a legfontosabb modulfejlesztési szerződésekhez.
- `app_conventions.py`: app modul fájlstruktúra, module key, route tag és hook név konvenciók.
- `app_keys.py`: app modulok `module.*` service kulcsai és helper függvénye.
- `base_app_module.py`: app modul alaposztály és lifecycle szerződés.
- `keys.py`: platform `platform.*` service kulcsok és typed helper.
- `module_context.py`: modulregisztrációs DI context service, repository, factory és state kezeléshez.
- `observability.py`: public observability dataclassok, Protocolok és vékony logging/metric wrapperök.
- `public_api.py`: architektúra tesztek által használt publikus import boundary lista.
- `routing.py`: route regisztrációs dataclass.
- `state_keys.py`: belső `ModuleContext.state` kulcsok platform feature átadáshoz.

## Kapcsolódás a nagy egészhez

A `bootstrap` réteg `BaseAppModule` és `ModuleContext` alapján regisztrálja a modulokat. Az `app` és `http` réteg `RouteRegistration` alapján köti be a routereket. Az app modulok a service kulcsokat és konvenciókat használják, hogy a DI és route kötés raw stringek helyett stabil, közös névtérre épüljön.

## Tervezési megjegyzés
Az `interface` fájloknak kicsinek és importbiztosnak kell maradniuk. Ha egy új elem runtime objektumot épít, adatbázist érint, settingset olvas vagy middleware-t regisztrál, akkor nem ide való, hanem inkább `bootstrap`, `http`, `runtime`, `deps` vagy más konkrét kernel réteg alá.

# Sárközi Mihály - 2026.05.21