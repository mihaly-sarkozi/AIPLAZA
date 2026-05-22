# shared/object_storage

A `shared/object_storage` csomag általános object storage adapterréteg. S3-kompatibilis backendhez, például MinIO-hoz vagy AWS S3-hoz ad port contractot, DTO-kat, konfigurációt és default factoryt.

## Fő felelősség

A modul célja, hogy app és core rétegek egységes módon tudjanak byte, text vagy file-like stream objektumokat feltölteni, letölteni, státuszt kérdezni és törölni. A `ObjectStoragePort` contract elválasztja az app service-eket a konkrét S3-kompatibilis implementációtól.

## Fájlok

- `__init__.py`: publikus exportfelület a config, port, DTO és factory típusokhoz.
- `config.py`: `ObjectStorageConfig` és settings-alapú konfiguráció betöltés.
- `contracts.py`: `ObjectStoragePort` Protocol, byte/text és file-like stream feltöltési műveletekkel.
- `models.py`: `StoredObjectRef` és `StoredObjectData` DTO-k.
- `s3_compatible.py`: boto3 alapú S3-kompatibilis adapter.
- `service.py`: cache-elt `get_object_storage()` factory.

## Kapcsolódás a nagy egészhez

Jelenleg főleg a knowledge app használja nagyobb dokumentum és ingest objektumok tárolására, de a contract általános: bármely app modul használhatja blob vagy dokumentum jellegű tartalomhoz. A testszintű noop adapterek is a shared DTO-kra és portra épülnek.

## Production Elvárások

Production környezetben az object storage nem lehet opcionális vagy helyi fájlrendszer fallback. A deploymentnek S3/MinIO/GCS-kompatibilis providert, bucket-level lifecycle policyt, encryption-at-rest beállítást és tenant prefix alapú izolációt kell biztosítania. A knowledge upload kulcsok tenant prefixet tartalmaznak; content-hash alapú deduplikációt későbbi storage service rétegben érdemes központosítani.

## Boundary Értékelés

A modul shared helye indokolt, mert storage contract és adapter, nem knowledge-domain logika. Egy határterület van: `config.py` közvetlenül a kernel settingsből olvas. Ez backend-shared adapterként elfogadható, de ha a shared réteget teljesen core-függetlenné akarjuk tenni, később érdemes a konfigurációt kívülről injektálni és a settings bridge-et core/bootstrap alá vinni.

## Shared Szabály

Ide csak általános storage művelet, storage DTO, provider adapter vagy kulcsépítés kerüljön. Knowledge ingest, tenant, PII, dokumentumértelmezési vagy üzleti retention szabály ne ebben a csomagban legyen.

## Sárközi Mihály - 2026.05.21
