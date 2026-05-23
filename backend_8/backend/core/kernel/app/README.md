# core/kernel/app

## Feladat
Az `app` könyvtár az alkalmazás összeállításának kernel szintű belépési pontjait tartalmazza. Itt nem üzleti funkciók vannak, hanem azok az általános keretrendszer-elemek, amelyek egy manifestből futtatható FastAPI alkalmazást, runtime konténert és lifespan kezelést építenek.

## Fájlok
- `app_manifest.py`: Az alkalmazás deklaratív leírása. A core modulok, app modulok, route-ok, hookok, jogosultságok és tenant schema hookok innen kerülnek a runtime-ba.
- `app_factory.py`: A FastAPI alkalmazás composition rootja. Security startup checket futtat, runtime konténert épít, middleware-eket, route-okat, exception handlereket és telemetriát köt be.
- `app_container.py`: A runtime konténer. Összerakja az infrastruktúrát, security réteget, module contextet, DI bekötést, permission service-t és lifecycle kontrollert.
- `app_lifespan.py`: A FastAPI lifespan adaptere. Startupkor inicializálja a runtime storage-ot és háttérszolgáltatásokat, shutdownkor leállítja őket és lezárja a közös Redis kapcsolatot.
- `app_bootstrap.py`: A manifest bootstrap hookjait és tenant schema hook regisztrációját futtatja.
- `__init__.py`: Rövid publikus importfelület az app kernel API-hoz.

## Kapcsolódás
A `backend/main.py` az `AppManifest` és a `create_app_from_manifest()` segítségével indítja az alkalmazást. Az `app_factory.py` hívja a runtime wiringot, a bootstrappet, a middleware/route regisztrációt és a lifespan adaptert. A HTTP dependency réteg és több core modul a `get_container()` / `container` elérésen keresztül jut a runtime-ban regisztrált szolgáltatásokhoz.


## Sárközi Mihály - 2026.05.21
