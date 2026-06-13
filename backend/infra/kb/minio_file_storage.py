from __future__ import annotations

# backend/infra/kb/minio_file_storage.py
# Feladat: FileStorageInterface MinIO/S3 implementáció.
# Sárközi Mihály - 2026.06.07

import base64
import hashlib
import os
import re
import tempfile
from typing import Any

from apps.kb.kb_understanding.extract.temp_file_utils import safe_delete_temp_file
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


def _is_ascii(value: str) -> bool:
    try:
        value.encode("ascii")
        return True
    except UnicodeEncodeError:
        return False


def _ascii_metadata_value(value: str) -> str:
    text = str(value)
    if _is_ascii(text):
        return text
    encoded = base64.urlsafe_b64encode(text.encode("utf-8")).decode("ascii").rstrip("=")
    return f"b64url:{encoded}"


def _ascii_storage_filename(filename: str) -> str:
    name = _sanitize_filename(filename)
    if _is_ascii(name):
        return name
    _stem, ext = os.path.splitext(name)
    digest = hashlib.sha256(name.encode("utf-8")).hexdigest()[:16]
    return f"{digest}{ext.lower()}" if ext else digest


def _metadata(**values: Any) -> dict[str, str]:
    return {key: _ascii_metadata_value(str(value)) for key, value in values.items() if value is not None}


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
        safe_name = _ascii_storage_filename(filename)
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
                filename=filename,
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

    def stat_bytes(self, *, raw_ref: str) -> int:
        key = str(raw_ref or "").strip()
        if not key:
            raise KbStorageError("raw_ref_required")
        try:
            return int(self._minio.stat_object(key=key).size_bytes or 0)
        except Exception as exc:
            raise KbStorageError("raw_ref_stat_failed") from exc

    def open_stream(self, *, raw_ref: str):
        key = str(raw_ref or "").strip()
        if not key:
            raise KbStorageError("raw_ref_required")
        temp_path = self.materialize_to_temp_file(raw_ref=key)
        return open(temp_path, "rb")

    def materialize_to_temp_file(self, *, raw_ref: str) -> str:
        key = str(raw_ref or "").strip()
        if not key:
            raise KbStorageError("raw_ref_required")
        suffix = os.path.splitext(key)[1] or ".bin"
        fd, path = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        try:
            self._minio.download_to_file(key=key, path=path)
        except Exception as exc:
            safe_delete_temp_file(path)
            raise KbStorageError("raw_ref_materialize_failed") from exc
        return path

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
        safe_name = _ascii_storage_filename(filename)
        return f"tenants/{tenant_slug}/kb/{kb_id}/training/{batch_id}/{item_id}/{safe_name}"


__all__ = ["MinioFileStorage"]
