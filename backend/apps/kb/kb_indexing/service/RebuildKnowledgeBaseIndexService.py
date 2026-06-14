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

        embeddable = self._embedding_jobs.list_latest_embeddable_for_knowledge_base(kb_id)
        rebuild = self._rebuilds.create(
            tenant_slug=request.tenant_slug,
            knowledge_base_id=kb_id,
            mode=mode,
            requested_by=request.requested_by,
            reason=request.reason,
            training_items_total=len(embeddable),
            metadata={"search_status": "INDEX_REBUILDING"},
        )
        self._patch_metrics(kb_id, request.tenant_slug, {"search_status": "INDEX_REBUILDING", "last_rebuild_job_id": rebuild.id})
        self._rebuilds.mark_running(rebuild.id)
        self._record_kb(request, "KB_INDEX_REBUILD_STARTED", {"rebuild_id": rebuild.id})

        if not embeddable:
            self._rebuilds.finish(
                rebuild.id,
                status=IndexRebuildStatus.FAILED,
                error_code=IndexingErrorCode.KB_INDEX_REBUILD_NO_EMBEDDED_ITEMS.value,
            )
            self._patch_metrics(kb_id, request.tenant_slug, {"search_status": "SEARCH_NOT_READY", "ready_for_search": False})
            return RebuildKnowledgeBaseIndexResultDto(
                rebuild_id=rebuild.id,
                status=IndexRebuildStatus.FAILED.value,
                error_code=IndexingErrorCode.KB_INDEX_REBUILD_NO_EMBEDDED_ITEMS.value,
            )

        collection_name = self._knowledge_bases.get_qdrant_collection_name(kb_id) or ""
        self._record_kb(request, "KB_INDEX_REBUILD_DELETE_STARTED", {})
        delete_result = self._delete.delete_for_knowledge_base(
            knowledge_base_id=kb_id,
            collection_name=collection_name,
            removed_by=request.requested_by,
            reason=request.reason or "kb_rebuild",
        )
        self._record_kb(
            request,
            "KB_INDEX_REBUILD_DELETE_COMPLETED",
            {"points_deleted": delete_result.qdrant_deleted},
        )

        reindexed = 0
        failed = 0
        points_reindexed = 0
        delete_failed = delete_result.partial

        for emb_job in embeddable:
            self._record_kb(
                request,
                "KB_INDEX_REBUILD_ITEM_STARTED",
                {"training_item_id": emb_job.training_item_id, "embedding_job_id": emb_job.id},
            )
            try:
                result = self._reindex.reindex(
                    ReindexTrainingItemRequestDto(
                        tenant_slug=request.tenant_slug,
                        knowledge_base_id=kb_id,
                        training_item_id=emb_job.training_item_id,
                        requested_by=request.requested_by,
                        reason=request.reason or "kb_rebuild",
                        force=True,
                        embedding_job_id=emb_job.id,
                    )
                )
            except Exception:
                logger.exception("KB rebuild item failed (item=%s)", emb_job.training_item_id)
                failed += 1
                continue

            if result.status == IndexingStatus.COMPLETED.value:
                reindexed += 1
                points_reindexed += result.points_deleted
                self._record_kb(
                    request,
                    "KB_INDEX_REBUILD_ITEM_COMPLETED",
                    {"training_item_id": emb_job.training_item_id, "indexing_job_id": result.indexing_job_id},
                )
            else:
                failed += 1

        if delete_failed and reindexed == 0:
            status = IndexRebuildStatus.FAILED
            error_code = IndexingErrorCode.KB_INDEX_REBUILD_DELETE_FAILED.value
        elif failed > 0 or delete_failed:
            status = IndexRebuildStatus.PARTIAL
            error_code = IndexingErrorCode.KB_INDEX_REBUILD_ITEM_FAILED.value if failed else IndexingErrorCode.KB_INDEX_REBUILD_DELETE_FAILED.value
        else:
            status = IndexRebuildStatus.COMPLETED
            error_code = None

        search_status = "READY_FOR_SEARCH" if status == IndexRebuildStatus.COMPLETED else "SEARCH_PARTIAL" if status == IndexRebuildStatus.PARTIAL else "SEARCH_NOT_READY"
        now = utc_now_naive().isoformat()
        self._rebuilds.finish(
            rebuild.id,
            status=status,
            error_code=error_code,
            training_items_reindexed=reindexed,
            training_items_failed=failed,
            points_deleted=delete_result.qdrant_deleted,
            points_reindexed=points_reindexed,
            metadata={"search_status": search_status, "rebuild_finished_at": now},
        )
        self._patch_metrics(
            kb_id,
            request.tenant_slug,
            {
                "search_status": search_status,
                "rebuild_finished_at": now,
                "ready_for_search": status == IndexRebuildStatus.COMPLETED,
                "last_rebuild_job_id": rebuild.id,
            },
        )
        event = "KB_INDEX_REBUILD_COMPLETED" if status == IndexRebuildStatus.COMPLETED else "KB_INDEX_REBUILD_PARTIAL" if status == IndexRebuildStatus.PARTIAL else "KB_INDEX_REBUILD_FAILED"
        self._record_kb(request, event, {"rebuild_id": rebuild.id, "status": status.value})

        return RebuildKnowledgeBaseIndexResultDto(
            rebuild_id=rebuild.id,
            status=status.value,
            error_code=error_code,
            training_items_total=len(embeddable),
            training_items_reindexed=reindexed,
            training_items_failed=failed,
            points_deleted=delete_result.qdrant_deleted,
        )

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


__all__ = ["RebuildKnowledgeBaseIndexService"]
