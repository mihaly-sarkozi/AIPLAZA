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
