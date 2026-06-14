from __future__ import annotations

from apps.kb.shared.contracts import IndexingChunkSnapshot, IndexingEmbeddingSnapshot
from apps.kb.kb_indexing.dto.IndexingDiscoveryBundleDto import IndexingDiscoveryBundleDto
from apps.kb.kb_indexing.dto.QdrantPointDto import QdrantPointDto
from apps.kb.kb_indexing.service.BuildQdrantPayloadService import BuildQdrantPayloadService
from apps.kb.shared.hash_utils import stable_point_id


class BuildQdrantPointService:
    def __init__(self, payload_service: BuildQdrantPayloadService) -> None:
        self._payload_service = payload_service

    def build(
        self,
        chunk: IndexingChunkSnapshot,
        embedding: IndexingEmbeddingSnapshot,
        bundle: IndexingDiscoveryBundleDto | None,
        *,
        knowledge_base_id: str,
        training_item_id: str,
    ) -> QdrantPointDto:
        payload_result = self._payload_service.build(
            chunk,
            embedding,
            bundle,
            knowledge_base_id=knowledge_base_id,
            training_item_id=training_item_id,
        )
        vector = list(embedding.embedding_vector)
        return QdrantPointDto(
            point_id=stable_point_id(chunk.chunk_id),
            vector=vector,
            payload=payload_result.payload,
            payload_hash=payload_result.payload_hash,
            vector_hash=embedding.vector_hash or "",
            chunk_id=chunk.chunk_id,
            embedding_id=embedding.id,
        )


__all__ = ["BuildQdrantPointService"]
