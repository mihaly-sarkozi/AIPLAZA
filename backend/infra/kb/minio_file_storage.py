from __future__ import annotations

# backend/infra/kb/minio_file_storage.py
# Feladat: FileStorageInterface MinIO/S3 implementáció.
# Sárközi Mihály - 2026.06.07

import re
from typing import Any

from apps.kb.shared.errors import KbStorageError
from shared.object_storage.service import get_object_storage

_UNSAFE_REF_SEGMENT = re.compile(r"[/\\]+")


def _safe_segment(value: str) -> str:
    segment = str(value or "").strip()
    if not segment:
        raise KbStorageError("raw_ref_segment_empty")
    cleaned = _UNSAFE_REF_SEGMENT.sub("_", segment)
    if cleaned in {".", ".."}:
        raise KbStorageError("raw_ref_segment_invalid")
    return cleaned


def _sanitize_filename(filename: str) -> str:
    name = str(filename or "").strip()
    if not name:
        raise KbStorageError("filename_empty")
    return _UNSAFE_REF_SEGMENT.sub("_", name)


def _metadata(**values: Any) -> dict[str, str]:
    return {key: str(value) for key, value in values.items() if value is not None}


class MinioFileStorage:
    """``FileStorageInterface`` — raw_ref építés + MinIO perzisztálás."""

    def __init__(self) -> None:
        self._minio = get_object_storage()

    def store_text(
        self,
        *,
        tenant: str,
        knowledge_base_id: str,
        training_batch_id: str,
        training_item_id: str,
        content: str,
        content_type: str = "text/plain",
    ) -> str:
        raw_ref = self._build_training_text_ref(
            tenant=tenant,
            knowledge_base_id=knowledge_base_id,
            training_batch_id=training_batch_id,
            training_item_id=training_item_id,
        )
        self._minio.put_text(
            key=raw_ref,
            text=content,
            content_type=content_type,
            metadata=_metadata(
                knowledge_base_id=knowledge_base_id,
                training_batch_id=training_batch_id,
                training_item_id=training_item_id,
            ),
        )
        return raw_ref

    def store_file(
        self,
        *,
        tenant: str,
        knowledge_base_id: str,
        training_batch_id: str,
        training_item_id: str,
        data: bytes,
        filename: str,
        content_type: str | None = None,
    ) -> str:
        safe_name = _sanitize_filename(filename)
        raw_ref = self._build_training_file_ref(
            tenant=tenant,
            knowledge_base_id=knowledge_base_id,
            training_batch_id=training_batch_id,
            training_item_id=training_item_id,
            filename=safe_name,
        )
        self._minio.put_bytes(
            key=raw_ref,
            content=data,
            content_type=content_type or "application/octet-stream",
            metadata=_metadata(
                knowledge_base_id=knowledge_base_id,
                training_batch_id=training_batch_id,
                training_item_id=training_item_id,
                filename=safe_name,
            ),
        )
        return raw_ref

    def read_bytes(self, *, raw_ref: str) -> bytes:
        key = str(raw_ref or "").strip()
        if not key:
            raise KbStorageError("raw_ref_required")
        try:
            stored = self._minio.get_bytes(key=key)
        except Exception as exc:
            raise KbStorageError("raw_ref_read_failed") from exc
        return stored.body

    @staticmethod
    def _build_training_text_ref(
        *,
        tenant: str,
        knowledge_base_id: str,
        training_batch_id: str,
        training_item_id: str,
    ) -> str:
        tenant_slug = _safe_segment(tenant or "default")
        kb_id = _safe_segment(knowledge_base_id)
        batch_id = _safe_segment(training_batch_id)
        item_id = _safe_segment(training_item_id)
        return f"tenants/{tenant_slug}/kb/{kb_id}/training/{batch_id}/{item_id}/input.txt"

    @staticmethod
    def _build_training_file_ref(
        *,
        tenant: str,
        knowledge_base_id: str,
        training_batch_id: str,
        training_item_id: str,
        filename: str,
    ) -> str:
        tenant_slug = _safe_segment(tenant or "default")
        kb_id = _safe_segment(knowledge_base_id)
        batch_id = _safe_segment(training_batch_id)
        item_id = _safe_segment(training_item_id)
        safe_name = _sanitize_filename(filename)
        return f"tenants/{tenant_slug}/kb/{kb_id}/training/{batch_id}/{item_id}/{safe_name}"


__all__ = ["MinioFileStorage"]
