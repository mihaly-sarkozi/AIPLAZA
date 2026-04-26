from __future__ import annotations

from typing import Any, Protocol

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

    def stat_object(self, *, key: str, bucket: str | None = None) -> StoredObjectRef: ...

    def delete_object(self, *, key: str, bucket: str | None = None) -> None: ...

    def build_key(self, *parts: str) -> str: ...


__all__ = ["ObjectStoragePort"]
