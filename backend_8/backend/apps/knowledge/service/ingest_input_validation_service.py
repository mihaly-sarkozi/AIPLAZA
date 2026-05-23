from __future__ import annotations

from dataclasses import replace
from typing import Any

from apps.knowledge.domain.ingest_input import IngestInput
from apps.knowledge.domain.ingest_item import IngestItem
from apps.knowledge.service.facade_helpers import normalize_text_payload
from apps.knowledge.service.facade_helpers import utcnow as utcnow


class IngestInputValidationService:
    def __init__(
        self,
        *,
        object_storage: Any,
        url_fetch_service: Any,
        ingest_item_store: Any,
        sha256_text: Any,
        sha256_bytes: Any,
    ) -> None:
        self._object_storage = object_storage
        self._url_fetch_service = url_fetch_service
        self._ingest_item_store = ingest_item_store
        self._sha256_text = sha256_text
        self._sha256_bytes = sha256_bytes

    def prepare_content_hash(self, item: IngestItem, ingest_input: IngestInput) -> tuple[str, IngestItem]:
        if ingest_input.input_type == "text":
            return self._sha256_text(normalize_text_payload(ingest_input.text_content)), item
        if ingest_input.input_type == "file":
            return self._file_hash(ingest_input), item
        if ingest_input.input_type == "url":
            return self._url_hash(item, ingest_input)
        raise ValueError(f"Unsupported ingest input type: {ingest_input.input_type}")

    def _file_hash(self, ingest_input: IngestInput) -> str:
        if not ingest_input.bucket_name or not ingest_input.object_key:
            raise ValueError("Missing object storage reference for file input")
        content_hash = str(ingest_input.checksum_sha256 or "")
        if content_hash:
            return content_hash
        stored = self._object_storage.get_bytes(
            key=ingest_input.object_key,
            bucket=ingest_input.bucket_name,
        )
        return self._sha256_bytes(stored.body)

    def _url_hash(self, item: IngestItem, ingest_input: IngestInput) -> tuple[str, IngestItem]:
        if not ingest_input.origin_url:
            raise ValueError("URL input is missing origin_url")
        response = self._url_fetch_service.request_head(ingest_input.origin_url, timeout=15)
        updated_item = self._ingest_item_store.update(
            replace(
                item,
                progress_message=f"URL elérhető, válasz: {response.status_code}.",
                updated_at=utcnow(),
                metadata={
                    **item.metadata,
                    "url_status_code": response.status_code,
                    "url_content_type": response.content_type,
                    "url_final_url": response.final_url,
                },
            )
        )
        return self._sha256_text(ingest_input.origin_url), updated_item


__all__ = ["IngestInputValidationService"]
