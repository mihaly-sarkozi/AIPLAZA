from __future__ import annotations

# backend/apps/kb/kb_understanding/service/EmbedChunksService.py
# Feladat: Chunk + summary embedding készítése batchben, modellverzió mentésével;
# részleges hiba esetén a sikeres embeddingek megmaradnak.
# Sárközi Mihály - 2026.06.11

import logging

from apps.kb.kb_understanding.dto.KnowledgeChunkDto import KnowledgeChunkDto
from apps.kb.kb_understanding.dto.KnowledgeEnrichmentDto import KnowledgeEnrichmentDto
from apps.kb.kb_understanding.dto.UnderstandingJobContext import UnderstandingJobContext
from apps.kb.kb_understanding.enums.UnderstandingErrorCode import UnderstandingErrorCode
from apps.kb.kb_understanding.errors.UnderstandingProcessingError import UnderstandingProcessingError
from apps.kb.kb_understanding.orm.KnowledgeEmbedding import KnowledgeEmbedding
from apps.kb.kb_understanding.ports.EmbeddingProviderInterface import EmbeddingProviderInterface
from apps.kb.kb_understanding.repository.EmbeddingRepository import EmbeddingRepository
from apps.kb.kb_understanding.validation.ValidateEmbeddings import ValidateEmbeddings
from apps.kb.shared.ids import new_id

logger = logging.getLogger(__name__)


class EmbedChunksService:
    def __init__(
        self,
        embedding_repository: EmbeddingRepository,
        embedder: EmbeddingProviderInterface,
    ) -> None:
        self._embedding_repository = embedding_repository
        self._embedder = embedder
        self._validate = ValidateEmbeddings()

    def run(
        self,
        ctx: UnderstandingJobContext,
        chunks: list[KnowledgeChunkDto],
        enrichments: list[KnowledgeEnrichmentDto] | None = None,
    ) -> int:
        """Visszaadja a mentett embedding rekordok számát."""
        if not chunks:
            raise UnderstandingProcessingError(UnderstandingErrorCode.NO_CHUNKS)

        targets: list[tuple[str, str, str]] = [
            (chunk.chunk_id, "chunk_text", chunk.text) for chunk in chunks
        ]
        for enrichment in enrichments or []:
            if (enrichment.summary or "").strip():
                targets.append((enrichment.chunk_id, "summary", enrichment.summary))

        vectors = self._embedder.embed_texts([text for _, _, text in targets])
        if len(vectors) != len(targets):
            raise UnderstandingProcessingError(
                UnderstandingErrorCode.EMBEDDING_FAILED, retryable=True
            )
        self._validate(vectors, expected_dimension=self._embedder.dimension)

        rows = [
            KnowledgeEmbedding(
                id=new_id("emb"),
                job_id=ctx.job_id,
                chunk_id=chunk_id,
                knowledge_base_id=ctx.knowledge_base_id,
                target=target,
                vector=vector,
                embedding_model=self._embedder.model_name,
                embedding_dimension=len(vector),
            )
            for (chunk_id, target, _), vector in zip(targets, vectors)
        ]
        return self._embedding_repository.replace_for_chunks(
            [chunk.chunk_id for chunk in chunks], rows
        )


__all__ = ["EmbedChunksService"]
