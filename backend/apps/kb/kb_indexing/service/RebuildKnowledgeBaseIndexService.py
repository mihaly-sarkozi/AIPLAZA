from __future__ import annotations

import logging

from apps.kb.kb_embedding.repository.EmbeddingJobRepository import EmbeddingJobRepository
from apps.kb.kb_indexing.dto.RebuildKnowledgeBaseIndexDtos import (
    RebuildKnowledgeBaseIndexRequestDto,
    RebuildKnowledgeBaseIndexResultDto,
)
from apps.kb.kb_indexing.dto.ReindexTrainingItemDtos import ReindexTrainingItemRequestDto
from apps.kb.kb_indexing.enums.IndexRebuildMode import IndexRebuildMode
from apps.kb.kb_indexing.enums.IndexRebuildStatus import IndexRebuildStatus
from apps.kb.kb_indexing.enums.IndexingErrorCode import IndexingErrorCode
from apps.kb.kb_indexing.enums.IndexingStatus import IndexingStatus
from apps.kb.kb_indexing.ports.reader_ports import KnowledgeBaseReaderPort
from apps.kb.kb_indexing.repository.IndexRebuildRepository import IndexRebuildRepository
from apps.kb.kb_indexing.service.DeleteIndexedChunksService import DeleteIndexedChunksService
from apps.kb.kb_indexing.service.ReindexTrainingItemService import ReindexTrainingItemService
from apps.kb.kb_processing.enums.ProcessingIssueCode import ProcessingIssueCode
from apps.kb.kb_processing.enums.ProcessingIssueSeverity import ProcessingIssueSeverity
from apps.kb.kb_processing.repository.ProcessingMetricsRepository import ProcessingMetricsRepository
from apps.kb.shared.ports.processing_flow_recorder import ProcessingFlowContext, ProcessingFlowRecorder
from shared.utils.clock import utc_now_naive

logger = logging.getLogger(__name__)

_PROCESSING_MODULE = "kb_indexing"


class RebuildKnowledgeBaseIndexService:
    def __init__(
        self,
        *,
        rebuild_repository: IndexRebuildRepository,
        embedding_job_repository: EmbeddingJobRepository,
        knowledge_base_reader: KnowledgeBaseReaderPort,
        delete_service: DeleteIndexedChunksService,
        reindex_service: ReindexTrainingItemService,
        metrics_repository: ProcessingMetricsRepository,
        flow_recorder: ProcessingFlowRecorder | None = None,
    ) -> None:
        self._rebuilds = rebuild_repository
        self._embedding_jobs = embedding_job_repository
        self._knowledge_bases = knowledge_base_reader
        self._delete = delete_service
        self._reindex = reindex_service
        self._metrics = metrics_repository
        self._flow_recorder = flow_recorder

    def rebuild(self, request: RebuildKnowledgeBaseIndexRequestDto) -> RebuildKnowledgeBaseIndexResultDto:
        kb_id = str(request.knowledge_base_id or "").strip()
        if not kb_id:
            raise ValueError("knowledge_base_id required")

        mode = str(request.mode or IndexRebuildMode.POINT_DELETE_AND_REINDEX.value).upper()
        if mode == IndexRebuildMode.RECREATE_COLLECTION.value:
            rebuild = self._rebuilds.create(
                tenant_slug=request.tenant_slug,
                knowledge_base_id=kb_id,
                mode=mode,
                requested_by=request.requested_by,
                reason=request.reason,
            )
            self._rebuilds.finish(
                rebuild.id,
                status=IndexRebuildStatus.FAILED,
                error_code=IndexingErrorCode.UNSUPPORTED_REBUILD_MODE.value,
                error_message="RECREATE_COLLECTION not supported yet",
            )
            return RebuildKnowledgeBaseIndexResultDto(
                rebuild_id=rebuild.id,
                status=IndexRebuildStatus.FAILED.value,
                error_code=IndexingErrorCode.UNSUPPORTED_REBUILD_MODE.value,
            )

        self._record_kb(request, "KB_INDEX_REBUILD_REQUESTED", {"mode": mode})

        active = self._rebuilds.has_active_for_knowledge_base(kb_id)
        if active and not request.force:
            return RebuildKnowledgeBaseIndexResultDto(
                rebuild_id=active,
                status=IndexRebuildStatus.RUNNING.value,
                error_code=IndexingErrorCode.KB_INDEX_REBUILD_ALREADY_RUNNING.value,
            )

        if not self._knowledge_bases.exists(kb_id):
            rebuild = self._rebuilds.create(
                tenant_slug=request.tenant_slug,
                knowledge_base_id=kb_id,
                mode=mode,
                requested_by=request.requested_by,
                reason=request.reason,
            )
            self._rebuilds.finish(
                rebuild.id,
                status=IndexRebuildStatus.FAILED,
                error_code=IndexingErrorCode.KNOWLEDGE_BASE_NOT_FOUND.value,
            )
            return RebuildKnowledgeBaseIndexResultDto(
                rebuild_id=rebuild.id,
                status=IndexRebuildStatus.FAILED.value,
                error_code=IndexingErrorCode.KNOWLEDGE_BASE_NOT_FOUND.value,
            )

        try:
            embeddable = self._embedding_jobs.list_latest_embeddable_for_knowledge_base(kb_id)
        except Exception:
            logger.exception("KB rebuild embeddable lookup failed (kb=%s)", kb_id)
            rebuild = self._rebuilds.create(
                tenant_slug=request.tenant_slug,
                knowledge_base_id=kb_id,
                mode=mode,
                requested_by=request.requested_by,
                reason=request.reason,
            )
            self._rebuilds.finish(
                rebuild.id,
                status=IndexRebuildStatus.FAILED,
                error_code=IndexingErrorCode.KB_INDEX_REBUILD_EMBEDDABLE_LOOKUP_FAILED.value,
                error_message="Failed to list embeddable training items",
            )
            self._open_rebuild_issue(
                request,
                issue_code=ProcessingIssueCode.KB_INDEX_REBUILD_EMBEDDABLE_LOOKUP_FAILED.value,
                severity=ProcessingIssueSeverity.ERROR.value,
                message="Failed to list embeddable training items for rebuild",
            )
            return RebuildKnowledgeBaseIndexResultDto(
                rebuild_id=rebuild.id,
                status=IndexRebuildStatus.FAILED.value,
                error_code=IndexingErrorCode.KB_INDEX_REBUILD_EMBEDDABLE_LOOKUP_FAILED.value,
            )

        rebuild = self._rebuilds.create(
            tenant_slug=request.tenant_slug,
            knowledge_base_id=kb_id,
            mode=mode,
            requested_by=request.requested_by,
            reason=request.reason,
            training_items_total=len(embeddable),
            metadata={"search_status": "INDEX_REBUILDING", "ready_for_search": False},
        )
        self._patch_metrics(
            kb_id,
            request.tenant_slug,
            {"search_status": "INDEX_REBUILDING", "ready_for_search": False, "last_rebuild_job_id": rebuild.id},
        )
        self._rebuilds.mark_running(rebuild.id)
        self._record_kb(request, "KB_INDEX_REBUILD_STARTED", {"rebuild_id": rebuild.id})

        if not embeddable:
            self._rebuilds.finish(
                rebuild.id,
                status=IndexRebuildStatus.FAILED,
                error_code=IndexingErrorCode.KB_INDEX_REBUILD_NO_EMBEDDED_ITEMS.value,
            )
            self._patch_metrics(kb_id, request.tenant_slug, {"search_status": "SEARCH_NOT_READY", "ready_for_search": False})
            self._open_rebuild_issue(
                request,
                issue_code=ProcessingIssueCode.KB_INDEX_REBUILD_NO_EMBEDDED_ITEMS.value,
                severity=ProcessingIssueSeverity.ERROR.value,
                message="No embeddable training items found for rebuild",
                job_id=rebuild.id,
            )
            return RebuildKnowledgeBaseIndexResultDto(
                rebuild_id=rebuild.id,
                status=IndexRebuildStatus.FAILED.value,
                error_code=IndexingErrorCode.KB_INDEX_REBUILD_NO_EMBEDDED_ITEMS.value,
                training_items_total=0,
            )

        collection_name = self._knowledge_bases.get_qdrant_collection_name(kb_id) or ""
        self._record_kb(request, "KB_INDEX_REBUILD_DELETE_STARTED", {})
        delete_result = self._delete.delete_for_knowledge_base(
            knowledge_base_id=kb_id,
            collection_name=collection_name,
            removed_by=request.requested_by,
            reason=request.reason or "kb_rebuild",
        )
        kb_points_deleted = int(delete_result.qdrant_deleted or 0)
        self._record_kb(
            request,
            "KB_INDEX_REBUILD_DELETE_COMPLETED",
            {"points_deleted": kb_points_deleted},
        )

        training_items_reindexed = 0
        training_items_failed = 0
        points_reindexed = 0
        points_verified = 0
        points_deleted_items = 0
        delete_failed = delete_result.partial

        for item in embeddable:
            self._record_kb(
                request,
                "KB_INDEX_REBUILD_ITEM_STARTED",
                {"training_item_id": item.training_item_id, "embedding_job_id": item.embedding_job_id},
            )
            try:
                result = self._reindex.reindex(
                    ReindexTrainingItemRequestDto(
                        tenant_slug=request.tenant_slug,
                        knowledge_base_id=kb_id,
                        training_item_id=item.training_item_id,
                        requested_by=request.requested_by,
                        reason=request.reason or "kb_rebuild",
                        force=True,
                        embedding_job_id=item.embedding_job_id,
                    )
                )
            except Exception:
                logger.exception("KB rebuild item failed (item=%s)", item.training_item_id)
                training_items_failed += 1
                self._open_rebuild_issue(
                    request,
                    issue_code=ProcessingIssueCode.KB_INDEX_REBUILD_ITEM_FAILED.value,
                    severity=ProcessingIssueSeverity.WARNING.value,
                    message=f"Rebuild failed for training item {item.training_item_id}",
                    training_item_id=item.training_item_id,
                    job_id=rebuild.id,
                )
                continue

            points_deleted_items += int(result.points_deleted or 0)
            points_reindexed += int(result.points_indexed or 0)
            points_verified += int(result.points_verified or 0)

            item_succeeded = (
                result.status in {IndexingStatus.COMPLETED.value, IndexingStatus.PARTIAL.value}
                and int(result.points_indexed or 0) > 0
            )
            if item_succeeded:
                training_items_reindexed += 1
                self._record_kb(
                    request,
                    "KB_INDEX_REBUILD_ITEM_COMPLETED",
                    {
                        "training_item_id": item.training_item_id,
                        "indexing_job_id": result.indexing_job_id,
                        "points_deleted": result.points_deleted,
                        "points_indexed": result.points_indexed,
                        "points_verified": result.points_verified,
                        "verification_id": result.verification_id,
                        "status": result.status,
                    },
                )
            else:
                training_items_failed += 1
                self._open_rebuild_issue(
                    request,
                    issue_code=ProcessingIssueCode.KB_INDEX_REBUILD_ITEM_FAILED.value,
                    severity=ProcessingIssueSeverity.WARNING.value,
                    message=result.error_message or f"Rebuild item failed ({result.error_code or result.status})",
                    training_item_id=item.training_item_id,
                    job_id=rebuild.id,
                    metadata={
                        "indexing_job_id": result.indexing_job_id,
                        "error_code": result.error_code,
                        "points_indexed": result.points_indexed,
                        "points_verified": result.points_verified,
                    },
                )

        points_deleted = max(kb_points_deleted, points_deleted_items)
        status, error_code = self._resolve_rebuild_status(
            training_items_total=len(embeddable),
            training_items_reindexed=training_items_reindexed,
            training_items_failed=training_items_failed,
            points_reindexed=points_reindexed,
            points_verified=points_verified,
            delete_failed=delete_failed,
        )

        if points_reindexed == 0:
            self._open_rebuild_issue(
                request,
                issue_code=ProcessingIssueCode.KB_INDEX_REBUILD_NO_POINTS_REINDEXED.value,
                severity=ProcessingIssueSeverity.ERROR.value,
                message="Rebuild completed without reindexed Qdrant points",
                job_id=rebuild.id,
            )
        elif points_verified < points_reindexed:
            self._open_rebuild_issue(
                request,
                issue_code=ProcessingIssueCode.KB_INDEX_REBUILD_VERIFICATION_INCOMPLETE.value,
                severity=ProcessingIssueSeverity.WARNING.value,
                message=f"Rebuild verification incomplete ({points_verified}/{points_reindexed})",
                job_id=rebuild.id,
                metadata={"points_reindexed": points_reindexed, "points_verified": points_verified},
            )

        if delete_failed:
            self._open_rebuild_issue(
                request,
                issue_code=ProcessingIssueCode.KB_INDEX_REBUILD_DELETE_FAILED.value,
                severity=ProcessingIssueSeverity.ERROR.value,
                message="KB-wide delete before rebuild was partial",
                job_id=rebuild.id,
            )

        ready_for_search = (
            status == IndexRebuildStatus.COMPLETED
            and points_reindexed > 0
            and points_verified == points_reindexed
            and training_items_failed == 0
        )
        search_status = (
            "READY_FOR_SEARCH"
            if ready_for_search
            else "SEARCH_PARTIAL"
            if status == IndexRebuildStatus.PARTIAL
            else "SEARCH_NOT_READY"
        )
        now = utc_now_naive().isoformat()
        audit_summary = {
            "rebuild_id": rebuild.id,
            "status": status.value,
            "training_items_total": len(embeddable),
            "training_items_reindexed": training_items_reindexed,
            "training_items_failed": training_items_failed,
            "points_deleted": points_deleted,
            "points_reindexed": points_reindexed,
            "points_verified": points_verified,
            "ready_for_search": ready_for_search,
            "search_status": search_status,
        }
        self._rebuilds.finish(
            rebuild.id,
            status=status,
            error_code=error_code,
            training_items_reindexed=training_items_reindexed,
            training_items_failed=training_items_failed,
            points_deleted=points_deleted,
            points_reindexed=points_reindexed,
            points_verified=points_verified,
            metadata={"search_status": search_status, "rebuild_finished_at": now, "ready_for_search": ready_for_search},
        )
        self._patch_metrics(
            kb_id,
            request.tenant_slug,
            {
                "search_status": search_status,
                "rebuild_finished_at": now,
                "ready_for_search": ready_for_search,
                "last_rebuild_job_id": rebuild.id,
            },
        )
        event = (
            "KB_INDEX_REBUILD_COMPLETED"
            if status == IndexRebuildStatus.COMPLETED
            else "KB_INDEX_REBUILD_PARTIAL"
            if status == IndexRebuildStatus.PARTIAL
            else "KB_INDEX_REBUILD_FAILED"
        )
        self._record_kb(request, event, audit_summary)

        return RebuildKnowledgeBaseIndexResultDto(
            rebuild_id=rebuild.id,
            status=status.value,
            error_code=error_code,
            training_items_total=len(embeddable),
            training_items_reindexed=training_items_reindexed,
            training_items_failed=training_items_failed,
            points_deleted=points_deleted,
            points_reindexed=points_reindexed,
            points_verified=points_verified,
        )

    @staticmethod
    def _resolve_rebuild_status(
        *,
        training_items_total: int,
        training_items_reindexed: int,
        training_items_failed: int,
        points_reindexed: int,
        points_verified: int,
        delete_failed: bool,
    ) -> tuple[IndexRebuildStatus, str | None]:
        if points_reindexed <= 0 or (
            training_items_total > 0 and training_items_failed >= training_items_total
        ):
            error_code = IndexingErrorCode.KB_INDEX_REBUILD_NO_POINTS_REINDEXED.value
            if delete_failed and points_reindexed <= 0:
                error_code = IndexingErrorCode.KB_INDEX_REBUILD_DELETE_FAILED.value
            return IndexRebuildStatus.FAILED, error_code

        if (
            training_items_failed > 0
            or delete_failed
            or points_verified < points_reindexed
        ):
            if points_verified < points_reindexed:
                return IndexRebuildStatus.PARTIAL, IndexingErrorCode.KB_INDEX_REBUILD_VERIFICATION_INCOMPLETE.value
            if training_items_failed > 0:
                return IndexRebuildStatus.PARTIAL, IndexingErrorCode.KB_INDEX_REBUILD_ITEM_FAILED.value
            return IndexRebuildStatus.PARTIAL, IndexingErrorCode.KB_INDEX_REBUILD_DELETE_FAILED.value

        if points_verified == points_reindexed and training_items_failed == 0:
            return IndexRebuildStatus.COMPLETED, None

        return IndexRebuildStatus.PARTIAL, IndexingErrorCode.KB_INDEX_REBUILD_VERIFICATION_INCOMPLETE.value

    def _patch_metrics(self, kb_id: str, tenant_slug: str | None, patch: dict) -> None:
        try:
            row = self._metrics.get_for_knowledge_base(kb_id)
            if row is None:
                from apps.kb.kb_processing.orm.ProcessingMetrics import ProcessingMetrics
                from apps.kb.shared.ids import new_id

                row = ProcessingMetrics(
                    id=new_id("proc_metrics"),
                    tenant_slug=tenant_slug,
                    knowledge_base_id=kb_id,
                )
            meta = dict(row.metadata_json or {})
            meta.update(patch)
            row.metadata_json = meta
            row.updated_at = utc_now_naive()
            self._metrics.upsert(row)
        except Exception:
            logger.warning("Rebuild metrics patch failed (kb=%s)", kb_id, exc_info=True)

    def _record_kb(self, request: RebuildKnowledgeBaseIndexRequestDto, event_type: str, summary: dict) -> None:
        if self._flow_recorder is None:
            return
        ctx = ProcessingFlowContext(
            tenant_slug=request.tenant_slug,
            knowledge_base_id=request.knowledge_base_id,
            training_batch_id="",
            training_item_id="",
            job_id=request.knowledge_base_id,
            created_by=request.requested_by,
        )
        self._flow_recorder.record_stage_completed(
            ctx,
            module=_PROCESSING_MODULE,
            stage="INDEXING",
            step="REBUILD",
            event_type=event_type,
            duration_ms=0,
            output_summary_json=summary,
        )

    def _open_rebuild_issue(
        self,
        request: RebuildKnowledgeBaseIndexRequestDto,
        *,
        issue_code: str,
        severity: str,
        message: str,
        training_item_id: str | None = None,
        job_id: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        if self._flow_recorder is None:
            return
        ctx = ProcessingFlowContext(
            tenant_slug=request.tenant_slug,
            knowledge_base_id=request.knowledge_base_id,
            training_batch_id="",
            training_item_id=training_item_id,
            job_id=job_id or request.knowledge_base_id,
            created_by=request.requested_by,
        )
        self._flow_recorder.open_issue(
            ctx,
            module=_PROCESSING_MODULE,
            stage="INDEXING",
            step="REBUILD",
            severity=severity,
            issue_code=issue_code,
            issue_message=message,
            metadata_json=metadata,
        )


__all__ = ["RebuildKnowledgeBaseIndexService"]
