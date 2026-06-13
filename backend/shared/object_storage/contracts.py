# backend/shared/object_storage/contracts.py
# Feladat: Az object storage backendek közös port contractját definiálja. Byte és text feltöltést, letöltést, stat műveletet, törlést és biztonságos kulcsépítést ír elő StoredObjectRef/StoredObjectData modellekkel. Shared adapter contract app és core modulok számára.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from typing import Any, BinaryIO, Protocol

from shared.object_storage.models import StoredObjectData, StoredObjectRef


class ObjectStoragePort(Protocol):
    def put_bytes(
        self,
        *,
        key: str,
        content: bytes,
        bucket: str | None = None,
        content_type: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> StoredObjectRef: ...

    def put_fileobj(
        self,
        *,
        key: str,
        fileobj: BinaryIO,
        bucket: str | None = None,
        content_type: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> StoredObjectRef: ...

    def put_text(
        self,
        *,
        key: str,
        text: str,
        bucket: str | None = None,
        encoding: str = "utf-8",
        content_type: str = "text/plain; charset=utf-8",
        metadata: dict[str, Any] | None = None,
    ) -> StoredObjectRef: ...

    def get_bytes(self, *, key: str, bucket: str | None = None) -> StoredObjectData: ...

    def download_to_file(self, *, key: str, path: str, bucket: str | None = None) -> StoredObjectRef: ...

    def stat_object(self, *, key: str, bucket: str | None = None) -> StoredObjectRef: ...

    def delete_object(self, *, key: str, bucket: str | None = None) -> None: ...

    def build_key(self, *parts: str) -> str: ...


__all__ = ["ObjectStoragePort"]
