from __future__ import annotations

from typing import Any

from apps.kb.kb_embedding.dto.EmbeddingResultDto import EmbeddingResultDto
from apps.kb.kb_embedding.repository.KnowledgeEmbeddingRepository import KnowledgeEmbeddingRepository


class StoreEmbeddingService:
    def __init__(self, embedding_repository: KnowledgeEmbeddingRepository) -> None:
        self._repository = embedding_repository

    def store_results(
        self,
        *,
        tenant_slug: str | None,
        knowledge_base_id: str,
        training_item_id: str,
        discovery_job_id: str,
        embedding_job_id: str,
        embedding_provider: str,
        embedding_model: str,
        results: list[EmbeddingResultDto],
        metadata: dict[str, Any] | None = None,
    ) -> int:
        stored = 0
        for result in results:
            self._repository.upsert_embedding(
                tenant_slug=tenant_slug,
                knowledge_base_id=knowledge_base_id,
                training_item_id=training_item_id,
                chunk_id=result.chunk_id,
                discovery_job_id=discovery_job_id,
                embedding_job_id=embedding_job_id,
                embedding_provider=embedding_provider,
                embedding_model=embedding_model,
                embedding_dimension=result.dimension,
                embedding_vector=result.vector,
                vector_hash=result.vector_hash,
                content_hash=result.content_hash,
                embedding_input_hash=result.input_hash,
                status="COMPLETED",
                metadata=metadata,
            )
            stored += 1
        return stored

    def store_failure(
        self,
        *,
        tenant_slug: str | None,
        knowledge_base_id: str,
        training_item_id: str,
        chunk_id: str,
        discovery_job_id: str,
        embedding_job_id: str,
        embedding_provider: str,
        embedding_model: str,
        embedding_dimension: int,
        error_code: str,
        error_message: str | None,
        content_hash: str | None = None,
        embedding_input_hash: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._repository.upsert_embedding(
            tenant_slug=tenant_slug,
            knowledge_base_id=knowledge_base_id,
            training_item_id=training_item_id,
            chunk_id=chunk_id,
            discovery_job_id=discovery_job_id,
            embedding_job_id=embedding_job_id,
            embedding_provider=embedding_provider,
            embedding_model=embedding_model,
            embedding_dimension=embedding_dimension,
            embedding_vector=None,
            vector_hash=None,
            content_hash=content_hash,
            embedding_input_hash=embedding_input_hash,
            status="FAILED",
            error_code=error_code,
            error_message=error_message,
            metadata=metadata,
        )


__all__ = ["StoreEmbeddingService"]
