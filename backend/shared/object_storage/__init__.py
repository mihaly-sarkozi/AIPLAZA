# backend/shared/object_storage/__init__.py
# Feladat: A shared object storage csomag publikus exportfelülete. Konfigurációt, port contractot, tárolt objektum DTO-kat és a default object storage factoryt adja tovább app és core rétegek számára. Általános backend shared adapter belépési pont S3-kompatibilis objektumtároláshoz.
# Sárközi Mihály - 2026.05.21

from shared.object_storage.config import ObjectStorageConfig, load_object_storage_config
from shared.object_storage.contracts import ObjectStoragePort
from shared.object_storage.models import StoredObjectData, StoredObjectRef
from shared.object_storage.service import get_object_storage

__all__ = [
    "ObjectStorageConfig",
    "ObjectStoragePort",
    "StoredObjectData",
    "StoredObjectRef",
    "get_object_storage",
    "load_object_storage_config",
]
