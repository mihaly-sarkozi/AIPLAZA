from __future__ import annotations

# backend/apps/kb/kb_reading/adapters/ObjectStorageReadingStorage.py
# Feladat: ReadingStorage port implementációja shared object storage-on.
# Sárközi Mihály - 2026.06.07

import io
from typing import BinaryIO

from shared.object_storage.contracts import ObjectStoragePort


class ObjectStorageReadingStorage:
    """``ReadingStorage`` → ``ObjectStoragePort`` adapter."""

    def __init__(self, object_storage: ObjectStoragePort) -> None:
        self._object_storage = object_storage

    def put_text(
        self,
        *,
        key: str,
        text: str,
        content_type: str = "text/plain",
        metadata: dict[str, str] | None = None,
    ) -> None:
        self._object_storage.put_text(
            key=key,
            text=text,
            content_type=content_type,
            metadata=metadata or {},
        )

    def put_bytes(
        self,
        *,
        key: str,
        content: bytes,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> None:
        self._object_storage.put_bytes(
            key=key,
            content=content,
            content_type=content_type,
            metadata=metadata or {},
        )

    def open_raw(self, key: str) -> BinaryIO:
        payload = self._object_storage.get_bytes(key=str(key).strip())
        return io.BytesIO(payload.content)

    def delete_raw(self, key: str) -> None:
        self._object_storage.delete_object(key=str(key).strip())


__all__ = ["ObjectStorageReadingStorage"]
