# core/kernel/lifecycle

A `lifecycle` kernel könyvtár az alkalmazás futásállapotát, health endpointjait és Prometheus metrics belépési pontját fogja össze. Azért került ki a `core/modules` alól, mert nem üzleti vagy tenant feature, hanem a teljes platform runtime működőképességét leíró kernel komponens.

## Fő felelősség

Ez a réteg liveness, readiness, összesített health és részletes lifecycle státusz válaszokat ad. A readiness döntést startup állapotból, DB probe-ból, cache probe-ból és background worker állapotból építi, miközben a `/metrics` és `/platform/lifecycle` endpointok prod környezetben token/IP védelemmel érhetők el.

## Fájlok

- `lifecycle.py`: `LifecycleCoreModule`, amely regisztrálja a service-t, routert, light pathokat és startup/shutdown hookokat.
- `lifecycle_state.py`: process startup/shutdown állapot és readiness check cache.
- `lifecycle_readiness_policy.py`: startup és background worker readiness döntési szabályok.
- `lifecycle_probe_repository.py`: DB/cache/background worker probe adapter.
- `lifecycle_service.py`: health, liveness, readiness és runtime status válaszok összeállítása.
- `lifecycle_router.py`: FastAPI endpointok és metrics hozzáférés-védelem.
- `health_response.py`, `liveness_response.py`, `readiness_response.py`, `lifecycle_status_response.py`: Pydantic response modellek a lifecycle API szerződéséhez.

## Kapcsolódás a nagy egészhez

Az `AppManifest` kötelező core komponensként tölti be a `LifecycleCoreModule`-t. A modul `PLATFORM_LIFECYCLE_SERVICE` kulcson publikálja a `LifecycleService`-t, a DB session factoryt és cache backendet az infrastruktúrából kapja, a background worker probe-ot pedig az `AppContainer` state-ből olvassa.

## Sárközi Mihály - 2026.05.21
