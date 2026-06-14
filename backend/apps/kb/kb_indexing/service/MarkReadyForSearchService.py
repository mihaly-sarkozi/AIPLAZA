from __future__ import annotations

import logging
from typing import Any

from apps.kb.kb_indexing.dto.IndexingVerificationDtos import QdrantVerificationResult, SearchReadinessResult
from apps.kb.kb_indexing.enums.IndexVerificationStatus import IndexVerificationStatus
from apps.kb.kb_indexing.enums.IndexingStatus import IndexingStatus
from apps.kb.kb_indexing.ports.reader_ports import EmbeddingJobReaderPort
from apps.kb.kb_indexing.repository.IndexingJobRepository import IndexingJobRepository
from apps.kb.kb_processing.repository.ProcessingMetricsRepository import ProcessingMetricsRepository
from apps.kb.shared.ports.processing_flow_recorder import ProcessingFlowContext, ProcessingFlowRecorder
from shared.utils.clock import utc_now_naive

logger = logging.getLogger(__name__)

_ALLOWED_EMBEDDING = frozenset({"COMPLETED", "PARTIAL"})
_PROCESSING_MODULE = "kb_indexing"


class MarkReadyForSearchService:
    def __init__(
        self,
        indexing_job_repository: IndexingJobRepository,
        embedding_job_reader: EmbeddingJobReaderPort,
        metrics_repository: ProcessingMetricsRepository,
        *,
        flow_recorder: ProcessingFlowRecorder | None = None,
    ) -> None:
        self._indexing_jobs = indexing_job_repository
        self._embedding_jobs = embedding_job_reader
        self._metrics = metrics_repository
        self._flow_recorder = flow_recorder

    def mark_if_ready(
        self,
        *,
        tenant_slug: str | None,
        knowledge_base_id: str,
        training_item_id: str,
        indexing_job_id: str,
        embedding_job_id: str,
        verification: QdrantVerificationResult,
        indexing_status: str | IndexingStatus | None = None,
        flow_ctx: ProcessingFlowContext | None = None,
    ) -> SearchReadinessResult:
        blocked: list[str] = []
        indexing_job = self._indexing_jobs.get_job(indexing_job_id)
        embedding_job = self._embedding_jobs.get_job(embedding_job_id)

        if embedding_job is None:
            blocked.append("EMBEDDING_JOB_NOT_FOUND")
        else:
            emb_status = str(embedding_job.get("status") or "")
            if emb_status not in _ALLOWED_EMBEDDING:
                blocked.append("EMBEDDING_NOT_READY")
            if int(embedding_job.get("chunks_embedded") or 0) <= 0:
                blocked.append("NO_EMBEDDINGS_FOR_INDEXING")

        resolved_indexing_status = (
            indexing_status.value if isinstance(indexing_status, IndexingStatus) else indexing_status
        )
        if resolved_indexing_status is None:
            if indexing_job is None:
                blocked.append("INDEXING_JOB_NOT_FOUND")
            elif indexing_job.status != IndexingStatus.COMPLETED.value:
                blocked.append("INDEXING_NOT_COMPLETED")
        elif resolved_indexing_status != IndexingStatus.COMPLETED.value:
            blocked.append("INDEXING_NOT_COMPLETED")

        if verification.status != IndexVerificationStatus.COMPLETED.value:
            blocked.append(verification.error_code or "QDRANT_VERIFICATION_FAILED")
        if verification.verified_points <= 0:
            blocked.append("NO_VERIFIED_POINTS")
        if verification.missing_points > 0:
            blocked.append("QDRANT_POINT_MISSING")
        if verification.payload_mismatches > 0:
            blocked.append("QDRANT_PAYLOAD_MISMATCH")
        if verification.vector_hash_mismatches > 0:
            blocked.append("QDRANT_VECTOR_HASH_MISMATCH")

        ready = not blocked
        now = utc_now_naive()
        metadata: dict[str, Any] = {
            "ready_for_search": ready,
            "qdrant_verified": verification.status == IndexVerificationStatus.COMPLETED.value,
            "search_ready_at": now.isoformat() if ready else None,
            "qdrant_verified_at": now.isoformat()
            if verification.status == IndexVerificationStatus.COMPLETED.value
            else None,
            "indexed_chunks_total": verification.expected_points,
            "qdrant_verified_chunks_total": verification.verified_points,
            "qdrant_missing_points_total": verification.missing_points,
            "qdrant_payload_mismatches_total": verification.payload_mismatches,
            "qdrant_vector_mismatches_total": verification.vector_hash_mismatches,
            "last_indexing_job_id": indexing_job_id,
            "last_index_verification_id": verification.verification_id,
            "training_item_id": training_item_id,
        }

        if ready:
            self._merge_metrics_metadata(knowledge_base_id, tenant_slug, metadata)
            self._record(flow_ctx, "READY_FOR_SEARCH_MARKED", metadata)
        else:
            self._merge_metrics_metadata(
                knowledge_base_id,
                tenant_slug,
                {**metadata, "ready_for_search": False, "blocking_reasons": blocked},
            )
            self._record(flow_ctx, "READY_FOR_SEARCH_BLOCKED", {"blocked": blocked})

        return SearchReadinessResult(
            ready_for_search=ready,
            qdrant_verified=verification.status == IndexVerificationStatus.COMPLETED.value,
            blocked_reasons=tuple(blocked),
            metadata=metadata,
        )

    def _merge_metrics_metadata(
        self,
        knowledge_base_id: str,
        tenant_slug: str | None,
        patch: dict[str, Any],
    ) -> None:
        try:
            existing = self._metrics.get_for_knowledge_base(knowledge_base_id)
            if existing is None:
                from apps.kb.kb_processing.orm.ProcessingMetrics import ProcessingMetrics
                from apps.kb.shared.ids import new_id

                existing = ProcessingMetrics(
                    id=new_id("proc_metrics"),
                    tenant_slug=tenant_slug,
                    knowledge_base_id=knowledge_base_id,
                )
            meta = dict(existing.metadata_json or {})
            meta.update(patch)
            existing.metadata_json = meta
            existing.updated_at = utc_now_naive()
            self._metrics.upsert(existing)
        except Exception:
            logger.warning("Search readiness metadata mentés sikertelen (kb=%s)", knowledge_base_id, exc_info=True)

    def _record(self, flow_ctx: ProcessingFlowContext | None, event_type: str, summary: dict) -> None:
        if flow_ctx is None or self._flow_recorder is None:
            return
        self._flow_recorder.record_stage_completed(
            flow_ctx,
            module=_PROCESSING_MODULE,
            stage="INDEXING",
            step="READY_FOR_SEARCH",
            event_type=event_type,
            duration_ms=0,
            output_summary_json=summary,
        )


__all__ = ["MarkReadyForSearchService"]
