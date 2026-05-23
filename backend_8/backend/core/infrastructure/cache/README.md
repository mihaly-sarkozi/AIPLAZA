# core/infrastructure/cache

A `cache` infrastruktúra modul a platform közös cache adapterrétege. Tenant routing, tenant status/config, domain-to-tenant, user és permission-change cache kulcsokat ad, valamint Redis vagy in-memory backend között választ.

## Fő felelősség

A modul két szintet tart: a közös `CacheBackend` contractot és factoryt a sima get/set/delete + TTL cache igényekhez, valamint egy natív Redis kliens helper réteget azokhoz a funkciókhoz, amelyek speciális Redis műveleteket használnak. Redis URL hiányában a közös cache in-memory fallbacket kap.

## Fájlok

- `__init__.py`: cache key prefixek, TTL-ek, key builder helper függvények, `get_cache()` / `set_cache()` singleton factory és lazy backend exportok.
- `ports.py`: `CacheBackend` absztrakt contract.
- `memory_backend.py`: thread-safe, egy processre érvényes in-memory cache backend.
- `redis_backend.py`: Redis alapú `CacheBackend` adapter.
- `redis_client.py`: natív Redis singleton kliens lazy init és shutdown kezelés.

## Kapcsolódás a nagy egészhez

A tenant routing és tenant cache invalidáció a közös key buildereket és `get_cache()` factoryt használja. A lifecycle readiness probe a cache backend roundtrip működését ellenőrzi. Az auth allowlist, rate limit, permission changed store és demo signup abuse control közvetlenül a natív `get_redis()` helperre épít, mert ezek nem puszta string TTL cache műveletek.

## Fontos Határ

Új általános cache használathoz a `get_cache()` és a `CacheBackend` contract legyen az alapértelmezett. Közvetlen `get_redis()` import csak akkor indokolt, ha Redis-specifikus művelet, atomikus számláló, allowlist vagy rate-limit jellegű adatstruktúra kell.

## Infrastruktúra Jelleg

Ez core infrastruktúra komponens. Nem tenant, auth vagy user üzleti logika, hanem közös cache storage és kliens lifecycle adapter, amelyet több modul használ.

## Sárközi Mihály - 2026.05.21
