from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

from apps.kb.kb_indexing.dto.IndexingJobContext import IndexingJobContext
from apps.kb.kb_indexing.enums.IndexVerificationStatus import IndexVerificationStatus
from apps.kb.kb_indexing.enums.IndexingErrorCode import IndexingErrorCode
from apps.kb.kb_indexing.enums.IndexingStatus import IndexingStatus
from apps.kb.kb_indexing.errors.IndexingProcessingError import IndexingProcessingError
from apps.kb.kb_indexing.events.indexing_completed_event import add_indexing_completed_event
from apps.kb.kb_indexing.repository.IndexingJobRepository import IndexingJobRepository
from apps.kb.kb_indexing.service.BuildQdrantPointService import BuildQdrantPointService
from apps.kb.kb_indexing.service.EnsureQdrantCollectionService import EnsureQdrantCollectionService
from apps.kb.kb_indexing.service.MarkReadyForSearchService import MarkReadyForSearchService
from apps.kb.kb_indexing.service.UpsertQdrantPointsService import UpsertQdrantPointsService
from apps.kb.kb_indexing.service.ValidateIndexingService import ValidateIndexingService
from apps.kb.kb_indexing.service.VerifyQdrantStorageService import VerifyQdrantStorageService
from apps.kb.kb_indexing.ports.reader_ports import ChunkReaderPort, DiscoveryBundleReaderPort, EmbeddingReaderPort
from apps.kb.shared.contracts import IndexingChunkSnapshot, IndexingEmbeddingSnapshot
from apps.kb.shared.ports.processing_flow_recorder import NoOpProcessingFlowRecorder, ProcessingFlowContext

logger = logging.getLogger(__name__)

_PROCESSING_MODULE = "kb_indexing"


class IndexingPipelineService:
    def __init__(
        self,
        job_repository: IndexingJobRepository,
        chunk_reader: ChunkReaderPort,
        embedding_reader: EmbeddingReaderPort,
        bundle_reader: DiscoveryBundleReaderPort,
        ensure_collection_service: EnsureQdrantCollectionService,
        build_point_service: BuildQdrantPointService,
        upsert_service: UpsertQdrantPointsService,
        validate_service: ValidateIndexingService,
        verify_service: VerifyQdrantStorageService,
        mark_ready_service: MarkReadyForSearchService,
        *,
        flow_recorder=None,
        metrics_updater: Callable[[str, str | None], None] | None = None,
        emit_indexing_completed: Callable[..., None] = add_indexing_completed_event,
    ) -> None:
        self._job_repository = job_repository
        self._chunk_reader = chunk_reader
        self._embedding_reader = embedding_reader
        self._bundle_reader = bundle_reader
        self._ensure_collection = ensure_collection_service
        self._build_point = build_point_service
        self._upsert = upsert_service
        self._validate = validate_service
        self._verify = verify_service
        self._mark_ready = mark_ready_service
        self._flow_recorder = flow_recorder or NoOpProcessingFlowRecorder()
        self._metrics_updater = metrics_updater
        self._emit_indexing_completed = emit_indexing_completed

    def run(self, ctx: IndexingJobContext) -> IndexingStatus:
        flow_ctx = ProcessingFlowContext(
            tenant_slug=ctx.tenant_slug,
            knowledge_base_id=ctx.knowledge_base_id,
            training_batch_id=ctx.training_batch_id,
            training_item_id=ctx.training_item_id,
            job_id=ctx.job_id,
            created_by=ctx.created_by,
        )
        self._job_repository.set_status(ctx.job_id, IndexingStatus.RUNNING)
        self._flow_recorder.record_stage_started(
            flow_ctx,
            module=_PROCESSING_MODULE,
            stage="INDEXING",
            step="PIPELINE",
            event_type="INDEXING_STARTED",
        )
        started = time.monotonic()

        embeddings = self._embedding_reader.list_successful_for_job(ctx.embedding_job_id)
        if not embeddings:
            self._job_repository.mark_finished(
                ctx.job_id,
                IndexingStatus.FAILED,
                error_code=IndexingErrorCode.NO_EMBEDDINGS_FOR_INDEXING.value,
            )
            return IndexingStatus.FAILED

        chunks = self._chunk_reader.list_for_document(ctx.training_item_id)
        chunk_map: dict[str, IndexingChunkSnapshot] = {chunk.chunk_id: chunk for chunk in chunks}
        chunk_ids = [emb.chunk_id for emb in embeddings if emb.chunk_id in chunk_map]
        bundles = self._bundle_reader.get_indexing_bundles_for_chunks(
            ctx.discovery_job_id,
            ctx.training_item_id,
            chunk_ids,
        )

        try:
            self._ensure_collection.ensure(
                ctx.collection_name,
                vector_size=ctx.vector_size,
                distance_metric=ctx.distance_metric,
            )
        except IndexingProcessingError as exc:
            self._finish_failed(ctx, flow_ctx, started, str(exc.code))
            return IndexingStatus.FAILED

        self._flow_recorder.record_stage_completed(
            flow_ctx,
            module=_PROCESSING_MODULE,
            stage="INDEXING",
            step="ENSURE_COLLECTION",
            event_type="QDRANT_COLLECTION_ENSURED",
            duration_ms=int((time.monotonic() - started) * 1000),
            output_summary_json={"collection": ctx.collection_name},
        )

        points = []
        for embedding in embeddings:
            chunk = chunk_map.get(embedding.chunk_id)
            if chunk is None:
                continue
            bundle = bundles.get(embedding.chunk_id)
            try:
                point = self._build_point.build(
                    chunk,
                    embedding,
                    bundle,
                    knowledge_base_id=ctx.knowledge_base_id,
                    training_item_id=ctx.training_item_id,
                )
                points.append(point)
            except Exception as exc:
                logger.exception("Payload build hiba chunk=%s", embedding.chunk_id)
                self._flow_recorder.open_issue(
                    flow_ctx,
                    module=_PROCESSING_MODULE,
                    stage="INDEXING",
                    step="BUILD_PAYLOAD",
                    severity="error",
                    issue_code=IndexingErrorCode.INDEX_PAYLOAD_BUILD_FAILED.value,
                    issue_message=str(exc),
                    metadata_json={"chunk_id": embedding.chunk_id},
                )

        self._flow_recorder.record_stage_completed(
            flow_ctx,
            module=_PROCESSING_MODULE,
            stage="INDEXING",
            step="BUILD_PAYLOAD",
            event_type="QDRANT_PAYLOAD_BUILT",
            duration_ms=0,
            output_summary_json={"points": len(points)},
        )

        indexed, failed = self._upsert.upsert(
            tenant_slug=ctx.tenant_slug,
            knowledge_base_id=ctx.knowledge_base_id,
            training_item_id=ctx.training_item_id,
            indexing_job_id=ctx.job_id,
            collection_name=ctx.collection_name,
            points=points,
        )
        self._job_repository.update_progress(
            ctx.job_id,
            chunks_indexed=indexed,
            chunks_failed=failed,
        )

        self._flow_recorder.record_stage_completed(
            flow_ctx,
            module=_PROCESSING_MODULE,
            stage="INDEXING",
            step="UPSERT",
            event_type="QDRANT_UPSERT_COMPLETED",
            duration_ms=int((time.monotonic() - started) * 1000),
            output_summary_json={"indexed": indexed, "failed": failed},
        )

        vector_hashes = {emb.id: emb.vector_hash or "" for emb in embeddings}
        _, validation_issues = self._validate.validate(
            ctx.job_id,
            embedding_ids=[emb.id for emb in embeddings],
            vector_hashes=vector_hashes,
        )

        if indexed == 0:
            status = IndexingStatus.FAILED
        elif failed > 0 or validation_issues:
            status = IndexingStatus.PARTIAL
        else:
            status = IndexingStatus.COMPLETED

        verification = None
        readiness = None
        if indexed > 0:
            verification = self._verify.verify(
                tenant_slug=ctx.tenant_slug,
                knowledge_base_id=ctx.knowledge_base_id,
                training_item_id=ctx.training_item_id,
                indexing_job_id=ctx.job_id,
                collection_name=ctx.collection_name,
                flow_ctx=flow_ctx,
            )
            if verification.status != IndexVerificationStatus.COMPLETED.value:
                status = IndexingStatus.PARTIAL if verification.verified_points > 0 else IndexingStatus.FAILED
            else:
                status = IndexingStatus.COMPLETED

            readiness = self._mark_ready.mark_if_ready(
                tenant_slug=ctx.tenant_slug,
                knowledge_base_id=ctx.knowledge_base_id,
                training_item_id=ctx.training_item_id,
                indexing_job_id=ctx.job_id,
                embedding_job_id=ctx.embedding_job_id,
                verification=verification,
                indexing_status=status,
                flow_ctx=flow_ctx,
            )
            if not readiness.ready_for_search and status == IndexingStatus.COMPLETED:
                status = IndexingStatus.PARTIAL

        error_code = None
        error_message = None
        if verification and verification.error_code:
            error_code = verification.error_code
            error_message = verification.error_message
        elif validation_issues and status != IndexingStatus.COMPLETED:
            error_code = validation_issues[0]
            error_message = ", ".join(validation_issues)

        self._job_repository.mark_finished(
            ctx.job_id,
            status,
            error_code=error_code,
            error_message=error_message,
        )

        issues = list(validation_issues)
        if verification:
            issues.extend(list(verification.issue_codes))
        if readiness and readiness.blocked_reasons:
            issues.extend(list(readiness.blocked_reasons))

        event_type = "INDEXING_COMPLETED" if status == IndexingStatus.COMPLETED else "INDEXING_FAILED"
        self._flow_recorder.record_stage_completed(
            flow_ctx,
            module=_PROCESSING_MODULE,
            stage="INDEXING",
            step="PIPELINE",
            event_type=event_type,
            duration_ms=int((time.monotonic() - started) * 1000),
            output_summary_json={
                "status": status.value,
                "issues": issues,
                "verification_status": verification.status if verification else None,
                "ready_for_search": readiness.ready_for_search if readiness else False,
            },
        )
        for issue in set(issues):
            severity = "error" if issue.startswith("QDRANT_") or issue == "INDEXING_FAILED" else "warning"
            self._flow_recorder.open_issue(
                flow_ctx,
                module=_PROCESSING_MODULE,
                stage="INDEXING",
                step="VALIDATION" if issue in validation_issues else "VERIFY_QDRANT",
                severity=severity,
                issue_code=issue,
            )
        if self._metrics_updater is not None:
            self._metrics_updater(ctx.knowledge_base_id, ctx.tenant_slug)
        self._flow_recorder.recalculate_metrics(flow_ctx)

        if status == IndexingStatus.COMPLETED and verification and readiness and readiness.ready_for_search:
            self._safe_emit(
                self._emit_indexing_completed,
                tenant_slug=ctx.tenant_slug,
                knowledge_base_id=ctx.knowledge_base_id,
                training_item_id=ctx.training_item_id,
                understanding_job_id=ctx.understanding_job_id,
                discovery_job_id=ctx.discovery_job_id,
                embedding_job_id=ctx.embedding_job_id,
                indexing_job_id=ctx.job_id,
                status=status.value,
                created_by=ctx.created_by,
            )

        return status

    def _finish_failed(
        self,
        ctx: IndexingJobContext,
        flow_ctx: ProcessingFlowContext,
        started: float,
        error_code: str,
    ) -> None:
        self._job_repository.mark_finished(
            ctx.job_id,
            IndexingStatus.FAILED,
            error_code=error_code,
        )
        self._flow_recorder.record_stage_failed(
            flow_ctx,
            module=_PROCESSING_MODULE,
            stage="INDEXING",
            step="PIPELINE",
            duration_ms=int((time.monotonic() - started) * 1000),
            error_code=error_code,
        )

    @staticmethod
    def _safe_emit(callback: Callable[..., None], **kwargs: Any) -> None:
        try:
            callback(**kwargs)
        except Exception:
            logger.exception("Indexing pipeline event emit hiba")


__all__ = ["IndexingPipelineService"]
