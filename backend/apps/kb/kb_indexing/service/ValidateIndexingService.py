from __future__ import annotations

from apps.kb.kb_indexing.enums.IndexingErrorCode import IndexingErrorCode
from apps.kb.kb_indexing.repository.IndexedChunkRepository import IndexedChunkRepository


class ValidateIndexingService:
    _MAX_FAILURE_RATIO = 0.5

    def __init__(self, indexed_chunk_repository: IndexedChunkRepository) -> None:
        self._repository = indexed_chunk_repository

    def validate(
        self,
        indexing_job_id: str,
        *,
        embedding_ids: list[str],
        vector_hashes: dict[str, str],
    ) -> tuple[bool, list[str]]:
        issues: list[str] = []
        rows = self._repository.list_for_job(indexing_job_id)
        indexed_embedding_ids = {row.embedding_id for row in rows if row.status == "INDEXED"}
        for embedding_id in embedding_ids:
            if embedding_id not in indexed_embedding_ids:
                issues.append(IndexingErrorCode.MISSING_EMBEDDING.value)
        for row in rows:
            if row.status == "INDEXED" and not row.payload_hash:
                issues.append(IndexingErrorCode.INDEX_PAYLOAD_BUILD_FAILED.value)
            expected_hash = vector_hashes.get(row.embedding_id)
            if expected_hash and row.vector_hash and row.vector_hash != expected_hash:
                issues.append(IndexingErrorCode.QDRANT_DIMENSION_MISMATCH.value)

        counts = self._repository.count_by_status(indexing_job_id)
        failed = counts.get("FAILED", 0)
        indexed = counts.get("INDEXED", 0)
        total = failed + indexed
        if total > 0 and failed / total > self._MAX_FAILURE_RATIO:
            issues.append(IndexingErrorCode.INDEXING_PARTIAL_FAILURE.value)

        return len(issues) == 0, issues


__all__ = ["ValidateIndexingService"]
