from __future__ import annotations

# backend/apps/kb/kb_reading/storage/RawWriter.py
# Feladat: Nyers anyag írása a ReadingStorage porton keresztül.
# Sárközi Mihály - 2026.06.07

from dataclasses import dataclass
from typing import Any

from apps.kb.kb_reading.storage.RawRefBuilder import (
    build_file_raw_ref,
    build_text_raw_ref,
    build_url_raw_ref,
    sanitize_filename,
)
from apps.kb.kb_reading.storage.ReadingStorage import ReadingStorage


@dataclass
class RawWriter:
    storage: ReadingStorage

    def write_text(
        self,
        *,
        tenant: str,
        knowledge_base_id: str,
        read_run_id: str,
        read_item_id: str,
        content: str,
        content_type: str = "text/plain",
    ) -> str:
        raw_ref = build_text_raw_ref(
            tenant=tenant,
            knowledge_base_id=knowledge_base_id,
            read_run_id=read_run_id,
            read_item_id=read_item_id,
        )
        self.storage.put_text(
            key=raw_ref,
            text=content,
            content_type=content_type,
            metadata=_metadata(
                knowledge_base_id=knowledge_base_id,
                read_run_id=read_run_id,
                read_item_id=read_item_id,
            ),
        )
        return raw_ref

    def write_file(
        self,
        *,
        tenant: str,
        knowledge_base_id: str,
        read_run_id: str,
        read_item_id: str,
        data: bytes,
        filename: str,
        content_type: str | None = None,
    ) -> str:
        safe_name = sanitize_filename(filename)
        raw_ref = build_file_raw_ref(
            tenant=tenant,
            knowledge_base_id=knowledge_base_id,
            read_run_id=read_run_id,
            read_item_id=read_item_id,
            filename=safe_name,
        )
        self.storage.put_bytes(
            key=raw_ref,
            content=data,
            content_type=content_type or "application/octet-stream",
            metadata=_metadata(
                knowledge_base_id=knowledge_base_id,
                read_run_id=read_run_id,
                read_item_id=read_item_id,
                filename=safe_name,
            ),
        )
        return raw_ref

    def write_url_response(
        self,
        *,
        tenant: str,
        knowledge_base_id: str,
        read_run_id: str,
        read_item_id: str,
        body: bytes,
        status_code: int,
        origin_url: str,
        final_url: str,
        content_type: str | None = None,
        response_headers: dict[str, str] | None = None,
    ) -> str:
        raw_ref = build_url_raw_ref(
            tenant=tenant,
            knowledge_base_id=knowledge_base_id,
            read_run_id=read_run_id,
            read_item_id=read_item_id,
        )
        metadata = _metadata(
            knowledge_base_id=knowledge_base_id,
            read_run_id=read_run_id,
            read_item_id=read_item_id,
            origin_url=origin_url,
            final_url=final_url,
            status_code=str(status_code),
        )
        if response_headers:
            metadata["response_headers"] = str(response_headers)
        self.storage.put_bytes(
            key=raw_ref,
            content=body,
            content_type=content_type or "application/octet-stream",
            metadata=metadata,
        )
        return raw_ref


def _metadata(**values: Any) -> dict[str, str]:
    return {key: str(value) for key, value in values.items() if value is not None}


__all__ = ["RawWriter"]
