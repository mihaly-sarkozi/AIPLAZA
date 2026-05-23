from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, BinaryIO

from shared.object_storage.contracts import ObjectStoragePort


class SourceStorageError(RuntimeError):
    """Object storage mentési hiba a source upload folyamatban."""


@dataclass(frozen=True)
class StoredSourceRef:
    storage_provider: str
    bucket_name: str
    object_key: str
    mime_type: str
    size_bytes: int
    checksum_sha256: str
    etag: str | None
    source_metadata: dict[str, Any]


class SourceStorageService:
    def __init__(self, object_storage: ObjectStoragePort) -> None:
        self._object_storage = object_storage

    @staticmethod
    def _sha256_bytes(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    def _build_storage_key(self, *, tenant: str, run_id: str, item_id: str, filename: str) -> tuple[str, str]:
        tenant_slug = (tenant or "default").strip() or "default"
        safe_filename = (filename or "upload.bin").strip().replace("/", "_")
        key = self._object_storage.build_key(
            "tenants",
            tenant_slug,
            "knowledge",
            "ingest",
            run_id,
            item_id,
            "raw",
            safe_filename,
        )
        return key, f"tenants/{tenant_slug}/knowledge"

    def store_uploaded_source(
        self,
        *,
        tenant: str,
        corpus_uuid: str,
        run_id: str,
        item_id: str,
        filename: str,
        mime_type: str | None,
        fileobj: BinaryIO | None = None,
        content: bytes | None = None,
        size_bytes: int = 0,
        checksum_sha256: str | None = None,
        seen_content_hashes: set[str] | None = None,
    ) -> StoredSourceRef:
        object_key, tenant_prefix = self._build_storage_key(
            tenant=tenant,
            run_id=run_id,
            item_id=item_id,
            filename=filename,
        )
        content_type = str(mime_type or "application/octet-stream")
        checksum = str(checksum_sha256 or "").strip()
        if fileobj is None:
            payload = bytes(content or b"")
            if not payload:
                raise ValueError(f"Empty file input: {filename}")
            checksum = checksum or self._sha256_bytes(payload)
            size_bytes = len(payload)
        elif size_bytes <= 0:
            raise ValueError(f"Empty file input: {filename}")
        if checksum and seen_content_hashes is not None:
            if checksum in seen_content_hashes:
                raise ValueError("Duplicate content hash in ingest batch.")
            seen_content_hashes.add(checksum)
        metadata = {
            "run_id": run_id,
            "item_id": item_id,
            "corpus_uuid": corpus_uuid,
            "checksum_sha256": checksum,
        }
        try:
            if fileobj is not None:
                if not hasattr(self._object_storage, "put_fileobj"):
                    raise ValueError("Object storage adapter does not support streaming file uploads.")
                seek = getattr(fileobj, "seek", None)
                if callable(seek):
                    seek(0)
                stored = self._object_storage.put_fileobj(
                    key=object_key,
                    fileobj=fileobj,
                    content_type=content_type,
                    metadata=metadata,
                )
            else:
                stored = self._object_storage.put_bytes(
                    key=object_key,
                    content=bytes(content or b""),
                    content_type=content_type,
                    metadata=metadata,
                )
        except ValueError:
            raise
        except Exception as exc:
            raise SourceStorageError(f"Object storage upload failed: {exc}") from exc
        resolved_checksum = checksum or str((stored.metadata or {}).get("checksum_sha256") or "").strip()
        resolved_size = int(stored.size_bytes or size_bytes or 0)
        source_metadata = {
            "storage_provider": stored.provider,
            "bucket_name": stored.bucket,
            "object_key": stored.key,
            "mime_type": stored.content_type or content_type,
            "size_bytes": resolved_size,
            "checksum_sha256": resolved_checksum,
            "etag": stored.etag,
            "tenant_prefix": tenant_prefix,
        }
        return StoredSourceRef(
            storage_provider=stored.provider,
            bucket_name=stored.bucket,
            object_key=stored.key,
            mime_type=str(stored.content_type or content_type),
            size_bytes=resolved_size,
            checksum_sha256=resolved_checksum,
            etag=stored.etag,
            source_metadata=source_metadata,
        )


__all__ = ["SourceStorageError", "SourceStorageService", "StoredSourceRef"]
