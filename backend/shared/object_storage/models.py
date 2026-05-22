# backend/shared/object_storage/models.py
# Feladat: Az object storage műveletek közös adatmodelljeit definiálja. A StoredObjectRef provider, bucket, key, etag, méret, content-type és metadata információt hordoz, a StoredObjectData pedig a ref mellett a letöltött byte tartalmat. Shared DTO contract storage adapterek és app service-ek között.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class StoredObjectRef:
    provider: str
    bucket: str
    key: str
    etag: str | None = None
    size_bytes: int | None = None
    content_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StoredObjectData:
    ref: StoredObjectRef
    body: bytes


__all__ = ["StoredObjectData", "StoredObjectRef"]
