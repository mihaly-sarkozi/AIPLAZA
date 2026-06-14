from __future__ import annotations

from typing import Protocol

from apps.kb.shared.contracts import IndexingChunkSnapshot, IndexingEmbeddingSnapshot
from apps.kb.kb_indexing.dto.IndexingDiscoveryBundleDto import IndexingDiscoveryBundleDto


class ChunkReaderPort(Protocol):
    def list_for_document(self, training_item_id: str) -> list[IndexingChunkSnapshot]: ...


class EmbeddingReaderPort(Protocol):
    def list_successful_for_job(self, embedding_job_id: str) -> list[IndexingEmbeddingSnapshot]: ...


class EmbeddingJobReaderPort(Protocol):
    def get_job(self, embedding_job_id: str) -> dict | None: ...


class DiscoveryBundleReaderPort(Protocol):
    def get_indexing_bundles_for_chunks(
        self,
        discovery_job_id: str,
        training_item_id: str,
        chunk_ids: list[str],
    ) -> dict[str, IndexingDiscoveryBundleDto]: ...


class KnowledgeBaseReaderPort(Protocol):
    def get_qdrant_collection_name(self, knowledge_base_id: str) -> str | None: ...

    def exists(self, knowledge_base_id: str) -> bool: ...


__all__ = [
    "ChunkReaderPort",
    "DiscoveryBundleReaderPort",
    "EmbeddingJobReaderPort",
    "EmbeddingReaderPort",
    "KnowledgeBaseReaderPort",
]
