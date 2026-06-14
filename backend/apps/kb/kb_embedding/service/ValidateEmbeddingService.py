from __future__ import annotations

from apps.kb.kb_embedding.dto.EmbeddingResultDto import EmbeddingResultDto
from apps.kb.kb_embedding.enums.EmbeddingErrorCode import EmbeddingErrorCode
from apps.kb.kb_embedding.repository.KnowledgeEmbeddingRepository import KnowledgeEmbeddingRepository


class ValidateEmbeddingService:
    _MAX_FAILURE_RATIO = 0.5

    def __init__(self, embedding_repository: KnowledgeEmbeddingRepository) -> None:
        self._repository = embedding_repository

    def validate(
        self,
        embedding_job_id: str,
        *,
        expected_dimension: int,
        chunk_ids: list[str],
        results: list[EmbeddingResultDto],
    ) -> tuple[bool, list[str]]:
        issues: list[str] = []
        result_map = {item.chunk_id: item for item in results}
        for chunk_id in chunk_ids:
            if chunk_id not in result_map:
                issues.append(EmbeddingErrorCode.MISSING_EMBEDDING.value)
        for item in results:
            if not item.vector:
                issues.append(EmbeddingErrorCode.EMPTY_EMBEDDING_VECTOR.value)
            elif item.dimension != expected_dimension:
                issues.append(EmbeddingErrorCode.EMBEDDING_DIMENSION_MISMATCH.value)
            elif not item.vector_hash:
                issues.append(EmbeddingErrorCode.EMPTY_EMBEDDING_VECTOR.value)

        counts = self._repository.count_by_status(embedding_job_id)
        failed = counts.get("FAILED", 0)
        completed = counts.get("COMPLETED", 0)
        total = failed + completed
        if total > 0 and failed / total > self._MAX_FAILURE_RATIO:
            issues.append(EmbeddingErrorCode.EMBEDDING_PARTIAL_FAILURE.value)

        return len(issues) == 0, issues


__all__ = ["ValidateEmbeddingService"]
