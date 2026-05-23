from __future__ import annotations

from apps.knowledge.domain.ingest_input import IngestInput
from apps.knowledge.domain.ingest_item import IngestItem
from apps.knowledge.domain.source import Source
from apps.knowledge.errors import KnowledgeValidationError


class IngestSourceFactory:
    def __init__(self, *, source_store) -> None:
        self._source_store = source_store

    def create_source(
        self,
        *,
        tenant: str,
        item: IngestItem,
        ingest_input: IngestInput,
        content_hash: str,
        created_by: int | None,
    ) -> Source:
        if ingest_input.input_type == "text":
            return self._source_store.create(
                Source(
                    tenant=tenant,
                    corpus_uuid=item.corpus_uuid,
                    title=item.title,
                    source_type="text",
                    raw_content=ingest_input.text_content,
                    file_ref=None,
                    status="attached",
                    created_by=created_by,
                    metadata=self._base_metadata(item, content_hash)
                    | {"char_count": len(str(ingest_input.text_content or ""))},
                )
            )
        if ingest_input.input_type == "file":
            metadata = self._base_metadata(item, content_hash) | {
                "storage_provider": ingest_input.storage_provider,
                "bucket_name": ingest_input.bucket_name,
                "object_key": ingest_input.object_key,
                "mime_type": ingest_input.mime_type,
                "size_bytes": ingest_input.size_bytes,
                "estimated_char_count": (
                    ingest_input.metadata.get("estimated_char_count")
                    if isinstance(ingest_input.metadata, dict)
                    else None
                ),
                "checksum_sha256": ingest_input.checksum_sha256,
            }
            return self._source_store.create(
                Source(
                    tenant=tenant,
                    corpus_uuid=item.corpus_uuid,
                    title=item.title,
                    source_type="file",
                    raw_content=None,
                    file_ref=ingest_input.original_filename,
                    status="attached",
                    created_by=created_by,
                    metadata=metadata,
                )
            )
        if ingest_input.input_type == "url":
            return self._source_store.create(
                Source(
                    tenant=tenant,
                    corpus_uuid=item.corpus_uuid,
                    title=item.title,
                    source_type="url",
                    raw_content=None,
                    file_ref=None,
                    status="attached",
                    created_by=created_by,
                    metadata=self._base_metadata(item, content_hash)
                    | {
                        "origin_url": ingest_input.origin_url,
                        "url_status_code": item.metadata.get("url_status_code"),
                        "url_content_type": item.metadata.get("url_content_type"),
                    },
                )
            )
        raise KnowledgeValidationError(f"Unsupported source type for ingest input: {ingest_input.input_type}")

    @staticmethod
    def _base_metadata(item: IngestItem, content_hash: str) -> dict[str, object]:
        return {
            "ingest_item_id": item.id,
            "ingest_run_id": item.ingest_run_id,
            "content_hash": content_hash,
        }


__all__ = ["IngestSourceFactory"]
