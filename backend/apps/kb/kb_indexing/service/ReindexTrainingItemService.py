from __future__ import annotations

import logging

from apps.kb.kb_embedding.repository.EmbeddingJobRepository import EmbeddingJobRepository
from apps.kb.kb_indexing.dto.ReindexTrainingItemDtos import (
    ReindexTrainingItemRequestDto,
    ReindexTrainingItemResultDto,
)
from apps.kb.kb_indexing.enums.IndexedChunkStatus import IndexedChunkStatus
from apps.kb.kb_indexing.enums.IndexingErrorCode import IndexingErrorCode
from apps.kb.kb_indexing.enums.IndexingStatus import IndexingStatus
from apps.kb.kb_indexing.errors.IndexingProcessingError import IndexingProcessingError
from apps.kb.kb_indexing.ports.reader_ports import KnowledgeBaseReaderPort
from apps.kb.kb_indexing.repository.IndexVerificationRepository import IndexVerificationRepository
from apps.kb.kb_indexing.repository.IndexingJobRepository import IndexingJobRepository
from apps.kb.kb_indexing.service.DeleteIndexedChunksService import DeleteIndexedChunksService
from apps.kb.kb_indexing.service.IndexingFailureRecorderService import IndexingFailureRecorderService
from apps.kb.kb_indexing.service.StartIndexingService import StartIndexingService
from apps.kb.shared.ports.processing_flow_recorder import ProcessingFlowContext, ProcessingFlowRecorder

logger = logging.getLogger(__name__)

_PROCESSING_MODULE = "kb_indexing"


class ReindexTrainingItemService:
    def __init__(
        self,
        *,
        embedding_job_repository: EmbeddingJobRepository,
        indexing_job_repository: IndexingJobRepository,
        verification_repository: IndexVerificationRepository,
        knowledge_base_reader: KnowledgeBaseReaderPort,
        delete_service: DeleteIndexedChunksService,
        start_indexing_service: StartIndexingService,
        failure_recorder: IndexingFailureRecorderService,
        flow_recorder: ProcessingFlowRecorder | None = None,
    ) -> None:
        self._embedding_jobs = embedding_job_repository
        self._indexing_jobs = indexing_job_repository
        self._verifications = verification_repository
        self._knowledge_bases = knowledge_base_reader
        self._delete = delete_service
        self._start = start_indexing_service
        self._failure_recorder = failure_recorder
        self._flow_recorder = flow_recorder

    def reindex(self, request: ReindexTrainingItemRequestDto) -> ReindexTrainingItemResultDto:
        kb_id = str(request.knowledge_base_id or "").strip()
        item_id = str(request.training_item_id or "").strip()
        if not kb_id or not item_id:
            raise IndexingProcessingError(IndexingErrorCode.INTERNAL_ERROR.value, reason="missing_ids")

        self._record(request, "REINDEX_TRAINING_ITEM_REQUESTED", {"reason": request.reason})

        active_job_id = self._indexing_jobs.get_active_job_id_for_training_item(item_id)
        if active_job_id and not request.force:
            raise IndexingProcessingError(
                IndexingErrorCode.JOB_ALREADY_RUNNING.value,
                indexing_job_id=active_job_id,
            )

        if not self._knowledge_bases.exists(kb_id):
            job = self._failure_recorder.create_failed_job(
                tenant_slug=request.tenant_slug,
                knowledge_base_id=kb_id,
                training_item_id=item_id,
                understanding_job_id="",
                discovery_job_id="",
                embedding_job_id=request.embedding_job_id or "",
                created_by=request.requested_by,
                error_code=IndexingErrorCode.KNOWLEDGE_BASE_NOT_FOUND.value,
            )
            return ReindexTrainingItemResultDto(
                indexing_job_id=job.id,
                status=IndexingStatus.FAILED.value,
                error_code=IndexingErrorCode.KNOWLEDGE_BASE_NOT_FOUND.value,
            )

        embedding_job = None
        if request.embedding_job_id:
            embedding_job = self._embedding_jobs.get_job(request.embedding_job_id)
        if embedding_job is None:
            embedding_job = self._embedding_jobs.get_latest_completed_for_training_item(
                item_id,
                knowledge_base_id=kb_id,
            )
        if embedding_job is None:
            job = self._failure_recorder.create_failed_job(
                tenant_slug=request.tenant_slug,
                knowledge_base_id=kb_id,
                training_item_id=item_id,
                understanding_job_id="",
                discovery_job_id="",
                embedding_job_id=request.embedding_job_id or "",
                created_by=request.requested_by,
                error_code=IndexingErrorCode.REINDEX_EMBEDDING_NOT_FOUND.value,
            )
            self._record(request, "REINDEX_FAILED", {"error_code": job.error_code})
            return ReindexTrainingItemResultDto(
                indexing_job_id=job.id,
                status=IndexingStatus.FAILED.value,
                error_code=IndexingErrorCode.REINDEX_EMBEDDING_NOT_FOUND.value,
            )

        collection_name = self._knowledge_bases.get_qdrant_collection_name(kb_id) or ""
        self._record(request, "REINDEX_TRAINING_ITEM_STARTED", {"embedding_job_id": embedding_job.id})
        self._record(request, "REINDEX_OLD_POINTS_DELETE_STARTED", {})

        delete_result = self._delete.delete_for_training_item(
            tenant_slug=request.tenant_slug,
            knowledge_base_id=kb_id,
            training_item_id=item_id,
            collection_name=collection_name,
            removed_by=request.requested_by,
            reason=request.reason or "reindex",
            new_status=IndexedChunkStatus.REPLACED.value,
        )
        points_deleted = int(delete_result.qdrant_deleted or 0)
        if delete_result.partial:
            self._record(
                request,
                "REINDEX_FAILED",
                {"error_code": IndexingErrorCode.REINDEX_DELETE_OLD_POINTS_FAILED.value},
            )
            job = self._failure_recorder.create_failed_job(
                tenant_slug=request.tenant_slug,
                knowledge_base_id=kb_id,
                training_item_id=item_id,
                understanding_job_id=embedding_job.understanding_job_id,
                discovery_job_id=embedding_job.discovery_job_id,
                embedding_job_id=embedding_job.id,
                created_by=request.requested_by,
                error_code=IndexingErrorCode.REINDEX_DELETE_OLD_POINTS_FAILED.value,
            )
            return ReindexTrainingItemResultDto(
                indexing_job_id=job.id,
                status=IndexingStatus.FAILED.value,
                error_code=IndexingErrorCode.REINDEX_DELETE_OLD_POINTS_FAILED.value,
                points_deleted=points_deleted,
                embedding_job_id=embedding_job.id,
            )

        self._record(request, "REINDEX_OLD_POINTS_DELETE_COMPLETED", {"points_deleted": points_deleted})
        self._record(request, "REINDEX_INDEXING_STARTED", {"embedding_job_id": embedding_job.id})

        status = self._start.start(
            tenant_slug=request.tenant_slug,
            knowledge_base_id=kb_id,
            training_item_id=item_id,
            understanding_job_id=embedding_job.understanding_job_id,
            discovery_job_id=embedding_job.discovery_job_id,
            embedding_job_id=embedding_job.id,
            created_by=request.requested_by,
        )
        latest_job = self._indexing_jobs.get_latest_for_training_item(item_id)
        indexing_job_id = latest_job.id if latest_job else ""
        points_indexed, points_verified, verification_id, error_message = self._indexing_metrics(indexing_job_id)

        if status == IndexingStatus.COMPLETED:
            self._record(
                request,
                "REINDEX_COMPLETED",
                {
                    "indexing_job_id": indexing_job_id,
                    "points_deleted": points_deleted,
                    "points_indexed": points_indexed,
                    "points_verified": points_verified,
                    "verification_id": verification_id,
                },
            )
            return ReindexTrainingItemResultDto(
                indexing_job_id=indexing_job_id,
                status=status.value,
                points_deleted=points_deleted,
                points_indexed=points_indexed,
                points_verified=points_verified,
                verification_id=verification_id,
                embedding_job_id=embedding_job.id,
            )

        error_code = (
            IndexingErrorCode.REINDEX_PARTIAL.value
            if status == IndexingStatus.PARTIAL
            else IndexingErrorCode.REINDEX_INDEXING_FAILED.value
        )
        self._record(
            request,
            "REINDEX_FAILED",
            {
                "error_code": error_code,
                "status": status.value,
                "points_indexed": points_indexed,
                "points_verified": points_verified,
            },
        )
        return ReindexTrainingItemResultDto(
            indexing_job_id=indexing_job_id,
            status=status.value,
            error_code=error_code,
            error_message=error_message,
            points_deleted=points_deleted,
            points_indexed=points_indexed,
            points_verified=points_verified,
            verification_id=verification_id,
            embedding_job_id=embedding_job.id,
        )

    def _indexing_metrics(self, indexing_job_id: str) -> tuple[int, int, str | None, str | None]:
        if not indexing_job_id:
            return 0, 0, None, None
        job = self._indexing_jobs.get_job(indexing_job_id)
        points_indexed = int(getattr(job, "chunks_indexed", 0) or 0) if job else 0
        error_message = getattr(job, "error_message", None) if job else None
        verification = self._verifications.get_latest_for_indexing_job(indexing_job_id)
        if verification is None:
            return points_indexed, 0, None, error_message
        return points_indexed, int(getattr(verification, "verified_points", 0) or 0), verification.id, error_message

    def _record(self, request: ReindexTrainingItemRequestDto, event_type: str, summary: dict) -> None:
        if self._flow_recorder is None:
            return
        ctx = ProcessingFlowContext(
            tenant_slug=request.tenant_slug,
            knowledge_base_id=request.knowledge_base_id,
            training_batch_id="",
            training_item_id=request.training_item_id,
            job_id=request.training_item_id,
            created_by=request.requested_by,
        )
        self._flow_recorder.record_stage_completed(
            ctx,
            module=_PROCESSING_MODULE,
            stage="INDEXING",
            step="REINDEX",
            event_type=event_type,
            duration_ms=0,
            output_summary_json=summary,
        )


__all__ = ["ReindexTrainingItemService"]
