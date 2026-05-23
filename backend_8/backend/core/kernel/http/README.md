# core/kernel/http

Az `http` könyvtár a kernel FastAPI/ASGI adapter rétege. Itt nincs üzleti logika: ez a csomag köti össze az app factoryt, a middleware láncot, a route regisztrációt, a dependency injectiont, a tenant contextet és az observability HTTP részét.

## Fő felelősség

Ez a réteg az alkalmazás HTTP felületének közös infrastruktúráját adja. Az `app_factory.py` innen regisztrál route-okat, middleware-eket és exception handlereket, míg a core és app routerek innen kapják a FastAPI dependency helper-eket.

## Fájlok

- `__init__.py`: csomagjelölő a kernel HTTP adapterekhez.
- `app_dependencies.py`: `module.*` service, repository és factory dependency-k FastAPI endpointokhoz.
- `core_route_registry.py`: core routerek és manifest routerek bekötése a FastAPI appba.
- `correlation_id_middleware.py`: request/correlation ID kezelés és observability context kötés.
- `exception_handlers.py`: globális JSON exception handlerek és hibametrikák.
- `middleware_registration.py`: globális middleware lánc sorrendje és konfigurációja.
- `request_timing_middleware.py`: API request timing logok, metrikák és debug timing headerek.
- `tenant_dependencies.py`: opcionális és kötelező tenant context dependency-k routerekhez.

## Kapcsolódás a nagy egészhez

Az `app/app_factory.py` hívja a `register_middlewares`, `register_exception_handlers` és `register_routes` függvényeket. A modul routerek `app_dependencies.py` és `tenant_dependencies.py` helperjeit importálják, hogy ne kelljen közvetlenül containerhez vagy tenant middleware belső állapothoz kötődniük.

# Sárközi Mihály - 2026.05.21