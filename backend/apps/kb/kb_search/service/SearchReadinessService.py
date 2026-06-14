from __future__ import annotations

import logging
from typing import Any

from apps.kb.kb_indexing.enums.IndexVerificationStatus import IndexVerificationStatus
from apps.kb.kb_indexing.enums.IndexingStatus import IndexingStatus
from apps.kb.kb_indexing.repository.IndexVerificationRepository import IndexVerificationRepository
from apps.kb.kb_indexing.repository.IndexingJobRepository import IndexingJobRepository
from apps.kb.kb_processing.repository.ProcessingMetricsRepository import ProcessingMetricsRepository
from apps.kb.kb_search.adapters.QdrantSearchAdapter import QdrantSearchAdapter
from apps.kb.kb_search.errors.SearchNotReadyError import SearchNotReadyError

logger = logging.getLogger(__name__)


class SearchReadinessService:
    def __init__(
        self,
        *,
        metrics_repository: ProcessingMetricsRepository,
        indexing_job_repository: IndexingJobRepository,
        verification_repository: IndexVerificationRepository,
        qdrant_search: QdrantSearchAdapter,
        knowledge_base_reader,
    ) -> None:
        self._metrics = metrics_repository
        self._indexing_jobs = indexing_job_repository
        self._verifications = verification_repository
        self._qdrant = qdrant_search
        self._kb_reader = knowledge_base_reader

    def check(
        self,
        *,
        knowledge_base_id: str,
        tenant_slug: str | None = None,
    ) -> dict[str, Any]:
        blocked: list[str] = []
        metrics = self._metrics.get_for_knowledge_base(knowledge_base_id)
        meta = dict(metrics.metadata_json or {}) if metrics is not None else {}

        if not bool(meta.get("ready_for_search")):
            blocked.append("READY_FOR_SEARCH_FALSE")
        if not bool(meta.get("qdrant_verified")):
            blocked.append("QDRANT_NOT_VERIFIED")
        indexed_total = int(meta.get("indexed_chunks_total") or 0)
        if indexed_total <= 0:
            blocked.append("NO_INDEXED_CHUNKS")

        last_job_id = str(meta.get("last_indexing_job_id") or "").strip()
        if last_job_id:
            job = self._indexing_jobs.get_job(last_job_id)
            if job is None:
                blocked.append("LAST_INDEXING_JOB_NOT_FOUND")
            elif job.status not in {IndexingStatus.COMPLETED.value, IndexingStatus.PARTIAL.value}:
                blocked.append("LAST_INDEXING_JOB_NOT_COMPLETED")
        else:
            blocked.append("NO_LAST_INDEXING_JOB")

        last_ver_id = str(meta.get("last_index_verification_id") or "").strip()
        if last_ver_id:
            verification = self._verifications.get(last_ver_id)
            if verification is None:
                blocked.append("LAST_VERIFICATION_NOT_FOUND")
            elif verification.status != IndexVerificationStatus.COMPLETED.value:
                blocked.append("LAST_VERIFICATION_NOT_COMPLETED")
        else:
            blocked.append("NO_LAST_VERIFICATION")

        collection = self._kb_reader.get_qdrant_collection_name(knowledge_base_id)
        if not collection:
            blocked.append("QDRANT_COLLECTION_MISSING")
        elif not self._qdrant.collection_exists(collection):
            blocked.append("QDRANT_COLLECTION_NOT_FOUND")
        elif self._qdrant.get_collection_point_count(collection) <= 0:
            blocked.append("QDRANT_EMPTY")

        ready = not blocked
        result = {
            "ready_for_search": ready,
            "qdrant_verified": bool(meta.get("qdrant_verified")),
            "indexed_chunks_total": indexed_total,
            "qdrant_collection": collection,
            "blocked_reasons": blocked,
            "metadata": meta,
        }
        if not ready:
            raise SearchNotReadyError(blocked_reasons=tuple(blocked), status="BLOCKED_NOT_READY")
        return result


__all__ = ["SearchReadinessService"]
