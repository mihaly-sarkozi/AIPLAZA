# backend/shared/object_storage/service.py
# Feladat: Default object storage adapter factoryt ad a backend számára. LRU cache-elt singletonként betölti a konfigurációt, ellenőrzi az engedélyezést és provider típust, majd S3CompatibleObjectStorage példányt hoz létre. Shared runtime factory app infrastruktúra assemblyhez.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from functools import lru_cache

from shared.object_storage.config import load_object_storage_config
from shared.object_storage.contracts import ObjectStoragePort
from shared.object_storage.s3_compatible import S3CompatibleObjectStorage


@lru_cache(maxsize=1)
def get_object_storage() -> ObjectStoragePort:
    config = load_object_storage_config()
    if not config.enabled:
        raise ValueError("Object storage is disabled")
    if config.provider != "s3_compatible":
        raise ValueError(f"Unsupported object storage provider: {config.provider}")
    return S3CompatibleObjectStorage(config)


__all__ = ["get_object_storage"]
