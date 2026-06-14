from __future__ import annotations

from apps.kb.shared.contracts import IndexingChunkSnapshot, IndexingEmbeddingSnapshot
from apps.kb.kb_indexing.dto.IndexingDiscoveryBundleDto import IndexingDiscoveryBundleDto
from apps.kb.kb_indexing.dto.QdrantPayloadDto import QdrantPayloadDto
from apps.kb.shared.hash_utils import payload_hash

_PREVIEW_MAX = 500


class BuildQdrantPayloadService:
    def build(
        self,
        chunk: IndexingChunkSnapshot,
        embedding: IndexingEmbeddingSnapshot,
        bundle: IndexingDiscoveryBundleDto | None,
        *,
        knowledge_base_id: str,
        training_item_id: str,
    ) -> QdrantPayloadDto:
        preview = (bundle.text_preview if bundle else chunk.text)[:_PREVIEW_MAX]
        payload = {
            "knowledge_base_id": knowledge_base_id,
            "training_item_id": training_item_id,
            "chunk_id": chunk.chunk_id,
            "document_id": bundle.document_id if bundle else chunk.chunk_id,
            "language_code": bundle.language_code if bundle else chunk.language_code,
            "language_confidence": bundle.language_confidence if bundle else chunk.language_confidence,
            "content_type": bundle.content_type if bundle else chunk.chunk_type,
            "content_type_confidence": bundle.content_type_confidence if bundle else None,
            "text_preview": preview,
            "heading_path": bundle.heading_path if bundle else None,
            "section_title": bundle.section_title if bundle else chunk.section_title,
            "page_numbers": bundle.page_numbers if bundle else (
                [chunk.page_number] if chunk.page_number is not None else []
            ),
            "source_part_ids": bundle.source_part_ids if bundle else [],
            "keywords": bundle.keywords if bundle else [],
            "topics": bundle.topics if bundle else [],
            "entities": bundle.entities if bundle else [],
            "temporal_mentions": bundle.temporal_mentions if bundle else [],
            "spatial_mentions": bundle.spatial_mentions if bundle else [],
            "process_mentions": bundle.process_mentions if bundle else [],
            "overall_score": bundle.overall_score if bundle else None,
            "score_components": bundle.score_components if bundle else {},
            "relationship_summary": bundle.relationship_summary if bundle else [],
            "source_type": bundle.source_type if bundle else None,
            "embedding_id": embedding.id,
            "vector_hash": embedding.vector_hash,
            "created_at": bundle.created_at if bundle else None,
            "updated_at": bundle.updated_at if bundle else None,
        }
        return QdrantPayloadDto(payload=payload, payload_hash=payload_hash(payload))


__all__ = ["BuildQdrantPayloadService"]
