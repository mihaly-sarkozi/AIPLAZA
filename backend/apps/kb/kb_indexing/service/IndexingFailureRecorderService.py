from __future__ import annotations

import logging
from typing import Any

from apps.kb.kb_indexing.enums.IndexingStatus import IndexingStatus
from apps.kb.kb_indexing.orm.IndexingJob import IndexingJob
from apps.kb.kb_indexing.ports.reader_ports import KnowledgeBaseReaderPort
from apps.kb.kb_indexing.repository.IndexingJobRepository import IndexingJobRepository
from apps.kb.shared.ports.processing_flow_recorder import ProcessingFlowContext, ProcessingFlowRecorder

logger = logging.getLogger(__name__)

_PROCESSING_MODULE = "kb_indexing"


class IndexingFailureRecorderService:
    """Failed indexing job + processing event/issue rögzítés."""

    def __init__(
        self,
        job_repository: IndexingJobRepository,
        knowledge_base_reader: KnowledgeBaseReaderPort,
        *,
        flow_recorder: ProcessingFlowRecorder | None = None,
    ) -> None:
        self._jobs = job_repository
        self._knowledge_bases = knowledge_base_reader
        self._flow_recorder = flow_recorder

    def record_request_received(
        self,
        *,
        tenant_slug: str | None,
        knowledge_base_id: str,
        training_item_id: str,
        embedding_job_id: str,
        created_by: int | None,
    ) -> None:
        self._emit(
            tenant_slug=tenant_slug,
            knowledge_base_id=knowledge_base_id,
            training_item_id=training_item_id,
            job_id=embedding_job_id,
            created_by=created_by,
            event_type="INDEXING_REQUEST_RECEIVED",
            summary={"embedding_job_id": embedding_job_id},
        )

    def create_failed_job(
        self,
        *,
        tenant_slug: str | None,
        knowledge_base_id: str,
        training_item_id: str,
        understanding_job_id: str,
        discovery_job_id: str,
        embedding_job_id: str,
        created_by: int | None,
        error_code: str,
        error_message: str | None = None,
        training_batch_id: str = "",
    ) -> IndexingJob:
        collection_name = self._knowledge_bases.get_qdrant_collection_name(knowledge_base_id) or ""
        job = self._jobs.create_job(
            tenant_slug=tenant_slug,
            knowledge_base_id=knowledge_base_id,
            training_item_id=training_item_id,
            understanding_job_id=understanding_job_id or "",
            discovery_job_id=discovery_job_id or "",
            embedding_job_id=embedding_job_id or "",
            created_by=created_by,
            collection_name=collection_name,
            vector_size=0,
            distance_metric="cosine",
            chunks_total=0,
            metadata={"failed_before_pipeline": True, "error_code": error_code},
        )
        self._jobs.mark_finished(
            job.id,
            IndexingStatus.FAILED,
            error_code=error_code,
            error_message=error_message or error_code,
        )
        self._emit(
            tenant_slug=tenant_slug,
            knowledge_base_id=knowledge_base_id,
            training_item_id=training_item_id,
            training_batch_id=training_batch_id,
            job_id=job.id,
            created_by=created_by,
            event_type="INDEXING_FAILED_BEFORE_JOB_START",
            summary={"error_code": error_code},
        )
        self._emit(
            tenant_slug=tenant_slug,
            knowledge_base_id=knowledge_base_id,
            training_item_id=training_item_id,
            training_batch_id=training_batch_id,
            job_id=job.id,
            created_by=created_by,
            event_type="INDEXING_FAILED",
            summary={"error_code": error_code, "indexing_job_id": job.id},
        )
        self._open_issue(
            tenant_slug=tenant_slug,
            knowledge_base_id=knowledge_base_id,
            training_item_id=training_item_id,
            training_batch_id=training_batch_id,
            job_id=job.id,
            created_by=created_by,
            issue_code=error_code,
            issue_message=error_message,
        )
        return job

    def record_job_created(
        self,
        *,
        tenant_slug: str | None,
        knowledge_base_id: str,
        training_item_id: str,
        training_batch_id: str,
        job_id: str,
        created_by: int | None,
    ) -> None:
        self._emit(
            tenant_slug=tenant_slug,
            knowledge_base_id=knowledge_base_id,
            training_item_id=training_item_id,
            training_batch_id=training_batch_id,
            job_id=job_id,
            created_by=created_by,
            event_type="INDEXING_JOB_CREATED",
            summary={"indexing_job_id": job_id},
        )

    def _emit(
        self,
        *,
        tenant_slug: str | None,
        knowledge_base_id: str,
        training_item_id: str,
        job_id: str,
        created_by: int | None,
        event_type: str,
        summary: dict[str, Any],
        training_batch_id: str = "",
    ) -> None:
        if self._flow_recorder is None:
            return
        ctx = ProcessingFlowContext(
            tenant_slug=tenant_slug,
            knowledge_base_id=knowledge_base_id,
            training_batch_id=training_batch_id,
            training_item_id=training_item_id,
            job_id=job_id,
            created_by=created_by,
        )
        self._flow_recorder.record_stage_completed(
            ctx,
            module=_PROCESSING_MODULE,
            stage="INDEXING",
            step="START",
            event_type=event_type,
            duration_ms=0,
            output_summary_json=summary,
        )

    def _open_issue(
        self,
        *,
        tenant_slug: str | None,
        knowledge_base_id: str,
        training_item_id: str,
        training_batch_id: str,
        job_id: str,
        created_by: int | None,
        issue_code: str,
        issue_message: str | None,
    ) -> None:
        if self._flow_recorder is None:
            return
        ctx = ProcessingFlowContext(
            tenant_slug=tenant_slug,
            knowledge_base_id=knowledge_base_id,
            training_batch_id=training_batch_id,
            training_item_id=training_item_id,
            job_id=job_id,
            created_by=created_by,
        )
        self._flow_recorder.open_issue(
            ctx,
            module=_PROCESSING_MODULE,
            stage="INDEXING",
            step="START",
            severity="error",
            issue_code=issue_code,
            issue_message=issue_message,
        )


__all__ = ["IndexingFailureRecorderService"]
