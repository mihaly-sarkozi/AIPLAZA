from __future__ import annotations

import io

import pytest

from apps.knowledge.service.source_storage_service import SourceStorageError, SourceStorageService
from shared.object_storage.models import StoredObjectRef
from shared.object_storage.s3_compatible import sanitize_object_key_part

pytestmark = pytest.mark.unit


class _StorageStub:
    def __init__(self) -> None:
        self.fail = False
        self.calls: list[dict[str, str]] = []

    def build_key(self, *parts: str) -> str:
        segments: list[str] = []
        for raw_part in parts:
            normalized = str(raw_part or "").strip().replace("\\", "/")
            for segment in normalized.split("/"):
                segments.append(sanitize_object_key_part(segment))
        return "/".join(segments)

    def put_bytes(self, *, key: str, content: bytes, bucket: str | None = None, content_type: str | None = None, metadata=None):
        if self.fail:
            raise RuntimeError("storage down")
        self.calls.append({"kind": "bytes", "key": key})
        return StoredObjectRef(
            provider="stub",
            bucket=bucket or "test-bucket",
            key=key,
            etag="etag-1",
            size_bytes=len(content),
            content_type=content_type,
            metadata=metadata or {},
        )

    def put_fileobj(self, *, key: str, fileobj, bucket: str | None = None, content_type: str | None = None, metadata=None):
        if self.fail:
            raise RuntimeError("storage down")
        fileobj.seek(0)
        content = fileobj.read()
        return self.put_bytes(
            key=key,
            content=content,
            bucket=bucket,
            content_type=content_type,
            metadata=metadata,
        )


def test_store_uploaded_source_successful_save() -> None:
    storage = _StorageStub()
    service = SourceStorageService(storage)

    stored = service.store_uploaded_source(
        tenant="demo",
        corpus_uuid="kb-1",
        run_id="run-1",
        item_id="item-1",
        filename="doc.txt",
        mime_type="text/plain",
        content=b"hello source",
        size_bytes=12,
    )

    assert stored.storage_provider == "stub"
    assert stored.bucket_name == "test-bucket"
    assert stored.object_key.endswith("/raw/doc.txt")
    assert stored.checksum_sha256
    assert stored.source_metadata["object_key"] == stored.object_key


def test_store_uploaded_source_wraps_storage_error() -> None:
    storage = _StorageStub()
    storage.fail = True
    service = SourceStorageService(storage)

    with pytest.raises(SourceStorageError):
        service.store_uploaded_source(
            tenant="demo",
            corpus_uuid="kb-1",
            run_id="run-1",
            item_id="item-1",
            filename="doc.txt",
            mime_type="text/plain",
            content=b"hello source",
            size_bytes=12,
        )


def test_store_uploaded_source_rejects_invalid_object_key() -> None:
    storage = _StorageStub()
    service = SourceStorageService(storage)

    with pytest.raises(ValueError, match="Invalid object key segment"):
        service.store_uploaded_source(
            tenant="..",
            corpus_uuid="kb-1",
            run_id="run-1",
            item_id="item-1",
            filename="doc.txt",
            mime_type="text/plain",
            content=b"hello source",
            size_bytes=12,
        )


def test_store_uploaded_source_rejects_duplicate_content_hash() -> None:
    storage = _StorageStub()
    service = SourceStorageService(storage)
    seen_hashes: set[str] = set()
    payload = b"duplicate-content"
    service.store_uploaded_source(
        tenant="demo",
        corpus_uuid="kb-1",
        run_id="run-1",
        item_id="item-1",
        filename="doc1.txt",
        mime_type="text/plain",
        content=payload,
        size_bytes=len(payload),
        seen_content_hashes=seen_hashes,
    )

    with pytest.raises(ValueError, match="Duplicate content hash"):
        service.store_uploaded_source(
            tenant="demo",
            corpus_uuid="kb-1",
            run_id="run-1",
            item_id="item-2",
            filename="doc2.txt",
            mime_type="text/plain",
            content=payload,
            size_bytes=len(payload),
            seen_content_hashes=seen_hashes,
        )


def test_store_uploaded_source_uses_tenant_path_prefix() -> None:
    storage = _StorageStub()
    service = SourceStorageService(storage)

    stored = service.store_uploaded_source(
        tenant="tenant-alpha",
        corpus_uuid="kb-1",
        run_id="run-1",
        item_id="item-1",
        filename="doc.txt",
        mime_type="text/plain",
        fileobj=io.BytesIO(b"content"),
        size_bytes=7,
    )

    assert stored.object_key.startswith("tenants/tenant-alpha/knowledge/")
    assert stored.source_metadata["tenant_prefix"] == "tenants/tenant-alpha/knowledge"


def test_store_uploaded_source_keeps_tenant_prefixes_isolated_between_tenants() -> None:
    storage = _StorageStub()
    service = SourceStorageService(storage)

    stored_a = service.store_uploaded_source(
        tenant="tenant-a",
        corpus_uuid="kb-1",
        run_id="run-1",
        item_id="item-a",
        filename="doc-a.txt",
        mime_type="text/plain",
        content=b"tenant-a-content",
        size_bytes=16,
    )
    stored_b = service.store_uploaded_source(
        tenant="tenant-b",
        corpus_uuid="kb-1",
        run_id="run-1",
        item_id="item-b",
        filename="doc-b.txt",
        mime_type="text/plain",
        content=b"tenant-b-content",
        size_bytes=16,
    )

    assert stored_a.object_key.startswith("tenants/tenant-a/knowledge/")
    assert stored_b.object_key.startswith("tenants/tenant-b/knowledge/")
    assert "tenants/tenant-b/" not in stored_a.object_key
    assert "tenants/tenant-a/" not in stored_b.object_key
