from __future__ import annotations

from typing import Protocol

from apps.kb.kb_embedding.dto.EmbeddingChunkDto import EmbeddingChunkDto
from apps.kb.kb_embedding.dto.EmbeddingDiscoveryBundleDto import EmbeddingDiscoveryBundleDto


class ChunkReaderPort(Protocol):
    def list_for_document(self, training_item_id: str) -> list[EmbeddingChunkDto]: ...


class DiscoveryJobReaderPort(Protocol):
    def get_job(self, discovery_job_id: str) -> dict | None: ...


class DiscoveryBundleReaderPort(Protocol):
    def get_bundles_for_chunks(
        self,
        discovery_job_id: str,
        training_item_id: str,
        chunk_ids: list[str],
    ) -> dict[str, EmbeddingDiscoveryBundleDto]: ...


__all__ = ["ChunkReaderPort", "DiscoveryBundleReaderPort", "DiscoveryJobReaderPort"]
