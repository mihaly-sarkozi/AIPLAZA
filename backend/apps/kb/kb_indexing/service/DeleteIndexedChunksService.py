from __future__ import annotations

import logging

from apps.kb.kb_indexing.adapters.QdrantAdapter import QdrantAdapter
from apps.kb.kb_indexing.enums.IndexedChunkStatus import IndexedChunkStatus
from apps.kb.kb_indexing.repository.IndexedChunkRepository import IndexedChunkRepository

logger = logging.getLogger(__name__)


class DeleteIndexedChunksService:
    """Qdrant pointok törlése és indexed chunk státusz DELETED."""

    def __init__(
        self,
        qdrant_adapter: QdrantAdapter,
        indexed_chunk_repository: IndexedChunkRepository,
    ) -> None:
        self._qdrant = qdrant_adapter
        self._indexed_chunks = indexed_chunk_repository

    def delete_for_training_item(
        self,
        *,
        tenant_slug: str | None,
        knowledge_base_id: str,
        training_item_id: str,
        indexing_job_id: str,
        collection_name: str,
        chunk_ids: list[str] | None = None,
    ) -> int:
        rows = self._indexed_chunks.list_for_job(indexing_job_id)
        targets = [
            row
            for row in rows
            if row.training_item_id == training_item_id
            and row.status == IndexedChunkStatus.INDEXED.value
            and (not chunk_ids or row.chunk_id in set(chunk_ids))
        ]
        if not targets:
            return 0
        point_ids = [row.qdrant_point_id for row in targets]
        try:
            self._qdrant.delete_points(collection_name, point_ids)
        except Exception:
            logger.exception("Qdrant point delete hiba")
            raise
        deleted = 0
        for row in targets:
            self._indexed_chunks.upsert_indexed_chunk(
                tenant_slug=tenant_slug,
                knowledge_base_id=knowledge_base_id,
                training_item_id=training_item_id,
                chunk_id=row.chunk_id,
                embedding_id=row.embedding_id,
                indexing_job_id=indexing_job_id,
                qdrant_collection=collection_name,
                qdrant_point_id=row.qdrant_point_id,
                payload_hash=row.payload_hash,
                vector_hash=row.vector_hash,
                status=IndexedChunkStatus.DELETED.value,
            )
            deleted += 1
        return deleted


__all__ = ["DeleteIndexedChunksService"]
