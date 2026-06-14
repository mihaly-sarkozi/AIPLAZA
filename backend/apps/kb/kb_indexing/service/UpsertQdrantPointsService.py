from __future__ import annotations

import logging

from apps.kb.kb_indexing.adapters.QdrantAdapter import QdrantAdapter
from apps.kb.kb_indexing.dto.QdrantPointDto import QdrantPointDto
from apps.kb.kb_indexing.enums.IndexedChunkStatus import IndexedChunkStatus
from apps.kb.kb_indexing.enums.IndexingErrorCode import IndexingErrorCode
from apps.kb.kb_indexing.errors.IndexingProcessingError import IndexingProcessingError
from apps.kb.kb_indexing.repository.IndexedChunkRepository import IndexedChunkRepository

logger = logging.getLogger(__name__)

_DEFAULT_BATCH_SIZE = 64


class UpsertQdrantPointsService:
    def __init__(
        self,
        qdrant_adapter: QdrantAdapter,
        indexed_chunk_repository: IndexedChunkRepository,
        *,
        batch_size: int = _DEFAULT_BATCH_SIZE,
    ) -> None:
        self._qdrant = qdrant_adapter
        self._indexed_chunks = indexed_chunk_repository
        self._batch_size = max(1, int(batch_size))

    def upsert(
        self,
        *,
        tenant_slug: str | None,
        knowledge_base_id: str,
        training_item_id: str,
        indexing_job_id: str,
        collection_name: str,
        points: list[QdrantPointDto],
    ) -> tuple[int, int]:
        indexed = 0
        failed = 0
        for offset in range(0, len(points), self._batch_size):
            batch = points[offset:offset + self._batch_size]
            try:
                self._qdrant.upsert_points(
                    collection_name,
                    [
                        {
                            "id": point.point_id,
                            "vector": point.vector,
                            "payload": point.payload,
                        }
                        for point in batch
                    ],
                )
                for point in batch:
                    self._indexed_chunks.upsert_indexed_chunk(
                        tenant_slug=tenant_slug,
                        knowledge_base_id=knowledge_base_id,
                        training_item_id=training_item_id,
                        chunk_id=point.chunk_id,
                        embedding_id=point.embedding_id,
                        indexing_job_id=indexing_job_id,
                        qdrant_collection=collection_name,
                        qdrant_point_id=point.point_id,
                        payload_hash=point.payload_hash,
                        vector_hash=point.vector_hash,
                        status=IndexedChunkStatus.INDEXED.value,
                    )
                    indexed += 1
            except Exception as exc:
                logger.exception("Qdrant upsert batch hiba")
                for point in batch:
                    self._indexed_chunks.upsert_indexed_chunk(
                        tenant_slug=tenant_slug,
                        knowledge_base_id=knowledge_base_id,
                        training_item_id=training_item_id,
                        chunk_id=point.chunk_id,
                        embedding_id=point.embedding_id,
                        indexing_job_id=indexing_job_id,
                        qdrant_collection=collection_name,
                        qdrant_point_id=point.point_id,
                        payload_hash=point.payload_hash,
                        vector_hash=point.vector_hash,
                        status=IndexedChunkStatus.FAILED.value,
                        error_code=IndexingErrorCode.QDRANT_UPSERT_FAILED.value,
                        error_message=str(exc),
                    )
                    failed += 1
                if offset == 0:
                    raise IndexingProcessingError(
                        IndexingErrorCode.QDRANT_UPSERT_FAILED.value,
                        message=str(exc),
                        retryable=True,
                    ) from exc
        return indexed, failed


__all__ = ["UpsertQdrantPointsService"]
