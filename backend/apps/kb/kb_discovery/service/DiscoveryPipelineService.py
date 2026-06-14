from __future__ import annotations

import logging
import time
from dataclasses import replace
from typing import Any, Callable

from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.dto.DiscoveryJobContext import DiscoveryJobContext
from apps.kb.kb_discovery.dto.DiscoveryResultDtos import RelationshipBuildInput
from apps.kb.kb_discovery.dto.LanguageDetectionResult import LanguageDetectionResult
from apps.kb.kb_discovery.enums.DiscoveryErrorCode import DiscoveryErrorCode
from apps.kb.kb_discovery.enums.DiscoveryStatus import DiscoveryStatus
from apps.kb.kb_discovery.enums.DiscoveryStep import DiscoveryStep
from apps.kb.kb_discovery.errors.DiscoveryProcessingError import DiscoveryProcessingError
from apps.kb.kb_discovery.events.discovery_completed_event import add_discovery_completed_event
from apps.kb.kb_discovery.events.discovery_failed_event import add_discovery_failed_event
from apps.kb.kb_discovery.events.embedding_requested_event import add_embedding_requested_event
from apps.kb.kb_discovery.repository.DiscoveryJobRepository import DiscoveryJobRepository
from apps.kb.kb_discovery.service.entity_output_summary import build_entity_extraction_output_summary
from apps.kb.shared.ports.processing_flow_recorder import (
    NoOpProcessingFlowRecorder,
    ProcessingFlowContext,
    ProcessingFlowRecorder,
)

logger = logging.getLogger(__name__)

_PROCESSING_MODULE = "kb_discovery"

_OPTIONAL_STEPS = frozenset(
    {
        DiscoveryStep.LANGUAGE_DETECTION,
        DiscoveryStep.ENTITY_EXTRACTION,
        DiscoveryStep.LOCAL_KNOWLEDGE_ENRICHMENT,
        DiscoveryStep.TEMPORAL_EXTRACTION,
        DiscoveryStep.SPATIAL_EXTRACTION,
        DiscoveryStep.PROCESS_EXTRACTION,
        DiscoveryStep.RELATIONSHIP_BUILD,
        DiscoveryStep.KNOWLEDGE_SCORING,
    }
)

_STEP_STATUS = {
    DiscoveryStep.LANGUAGE_DETECTION: DiscoveryStatus.DETECTING_LANGUAGE,
    DiscoveryStep.ENTITY_EXTRACTION: DiscoveryStatus.EXTRACTING_ENTITIES,
    DiscoveryStep.LOCAL_KNOWLEDGE_ENRICHMENT: DiscoveryStatus.ENRICHING_LOCAL,
    DiscoveryStep.TEMPORAL_EXTRACTION: DiscoveryStatus.EXTRACTING_TEMPORAL,
    DiscoveryStep.SPATIAL_EXTRACTION: DiscoveryStatus.EXTRACTING_SPATIAL,
    DiscoveryStep.PROCESS_EXTRACTION: DiscoveryStatus.EXTRACTING_PROCESS,
    DiscoveryStep.RELATIONSHIP_BUILD: DiscoveryStatus.BUILDING_RELATIONSHIPS,
    DiscoveryStep.KNOWLEDGE_SCORING: DiscoveryStatus.SCORING,
    DiscoveryStep.VALIDATION: DiscoveryStatus.VALIDATING,
}

_STEP_FLOW = {
    DiscoveryStep.LANGUAGE_DETECTION: (
        "LANGUAGE_DETECTION",
        "DETECT_LANGUAGE",
        "LANGUAGE_DETECTION_STARTED",
        "LANGUAGE_DETECTION_COMPLETED",
    ),
    DiscoveryStep.ENTITY_EXTRACTION: (
        "ENTITY_EXTRACTION",
        "EXTRACT_ENTITIES",
        "ENTITY_EXTRACTION_STARTED",
        "ENTITY_EXTRACTION_COMPLETED",
    ),
    DiscoveryStep.LOCAL_KNOWLEDGE_ENRICHMENT: (
        "LOCAL_KNOWLEDGE_ENRICHMENT",
        "ENRICH_LOCAL",
        "LOCAL_ENRICHMENT_STARTED",
        "LOCAL_ENRICHMENT_COMPLETED",
    ),
    DiscoveryStep.TEMPORAL_EXTRACTION: (
        "TEMPORAL_EXTRACTION",
        "EXTRACT_TEMPORAL",
        "TEMPORAL_EXTRACTION_STARTED",
        "TEMPORAL_EXTRACTION_COMPLETED",
    ),
    DiscoveryStep.SPATIAL_EXTRACTION: (
        "SPATIAL_EXTRACTION",
        "EXTRACT_SPATIAL",
        "SPATIAL_EXTRACTION_STARTED",
        "SPATIAL_EXTRACTION_COMPLETED",
    ),
    DiscoveryStep.PROCESS_EXTRACTION: (
        "PROCESS_EXTRACTION",
        "EXTRACT_PROCESS",
        "PROCESS_EXTRACTION_STARTED",
        "PROCESS_EXTRACTION_COMPLETED",
    ),
    DiscoveryStep.RELATIONSHIP_BUILD: (
        "RELATIONSHIP_BUILD",
        "BUILD_RELATIONSHIPS",
        "RELATIONSHIP_BUILD_STARTED",
        "RELATIONSHIP_BUILD_COMPLETED",
    ),
    DiscoveryStep.KNOWLEDGE_SCORING: (
        "KNOWLEDGE_SCORING",
        "SCORE_KNOWLEDGE",
        "KNOWLEDGE_SCORING_STARTED",
        "KNOWLEDGE_SCORING_COMPLETED",
    ),
    DiscoveryStep.VALIDATION: (
        "VALIDATION",
        "VALIDATE_DISCOVERY",
        "DISCOVERY_VALIDATION_STARTED",
        "DISCOVERY_VALIDATION_COMPLETED",
    ),
}


class DiscoveryPipelineService:
    def __init__(
        self,
        job_repository: DiscoveryJobRepository,
        *,
        language_service,
        entity_service,
        enrichment_service,
        temporal_service,
        spatial_service,
        process_service,
        relationship_service,
        scoring_service,
        validate_service,
        flow_recorder: ProcessingFlowRecorder | None = None,
        emit_completed: Callable[..., None] = add_discovery_completed_event,
        emit_failed: Callable[..., None] = add_discovery_failed_event,
        emit_embedding_requested: Callable[..., None] = add_embedding_requested_event,
    ) -> None:
        self._job_repository = job_repository
        self._language = language_service
        self._entity = entity_service
        self._enrichment = enrichment_service
        self._temporal = temporal_service
        self._spatial = spatial_service
        self._process = process_service
        self._relationship = relationship_service
        self._scoring = scoring_service
        self._validate = validate_service
        self._flow_recorder = flow_recorder or NoOpProcessingFlowRecorder()
        self._emit_completed = emit_completed
        self._emit_failed = emit_failed
        self._emit_embedding_requested = emit_embedding_requested

    def run(self, ctx: DiscoveryJobContext, chunks) -> DiscoveryStatus:
        flow_ctx = self._flow_context(ctx)
        had_optional_failures = False
        entities, mentions = [], []
        enrichment_result = None
        temporal_result = None
        spatial_result = None
        process_result = None
        relationship_result = None
        scores = []

        self._flow_recorder.record_stage_started(
            flow_ctx,
            module=_PROCESSING_MODULE,
            stage="DISCOVERY",
            step="PIPELINE",
            event_type="DISCOVERY_STARTED",
            input_summary_json={"chunk_count": len(chunks)},
        )

        try:
            language = self._run_step(
                ctx,
                flow_ctx,
                DiscoveryStep.LANGUAGE_DETECTION,
                lambda: self._language.run(ctx, chunks),
                input_summary={"chunk_count": len(chunks)},
                output_summary=lambda r: {
                    "chunks_checked": r.chunks_checked,
                    "document_language_code": r.language_code,
                    "document_language_confidence": r.language_confidence,
                    "language_distribution": dict(r.language_distribution),
                },
            )
            chunks = self._apply_language_results(chunks, language)
            ctx = replace(
                ctx,
                language_code=language.language_code,
                language_confidence=language.language_confidence,
            )
        except Exception:
            had_optional_failures = True

        try:
            entities, mentions = self._run_step(
                ctx,
                flow_ctx,
                DiscoveryStep.ENTITY_EXTRACTION,
                lambda: self._entity.run(ctx, chunks),
                input_summary={"chunk_count": len(chunks)},
                output_summary=lambda r: build_entity_extraction_output_summary(r[0], r[1]),
            )
        except Exception:
            had_optional_failures = True

        try:
            enrichment_result = self._run_step(
                ctx,
                flow_ctx,
                DiscoveryStep.LOCAL_KNOWLEDGE_ENRICHMENT,
                lambda: self._enrichment.run(ctx, chunks),
                input_summary={"chunk_count": len(chunks), "language_code": ctx.language_code},
                output_summary=lambda r: r.trace,
            )
        except Exception:
            had_optional_failures = True

        try:
            temporal_result = self._run_step(
                ctx,
                flow_ctx,
                DiscoveryStep.TEMPORAL_EXTRACTION,
                lambda: self._temporal.run(ctx, chunks),
                input_summary={"chunk_count": len(chunks)},
                output_summary=lambda r: r.trace,
            )
        except Exception:
            had_optional_failures = True

        try:
            spatial_result = self._run_step(
                ctx,
                flow_ctx,
                DiscoveryStep.SPATIAL_EXTRACTION,
                lambda: self._spatial.run(ctx, chunks),
                input_summary={"chunk_count": len(chunks)},
                output_summary=lambda r: r.trace,
            )
        except Exception:
            had_optional_failures = True

        try:
            process_result = self._run_step(
                ctx,
                flow_ctx,
                DiscoveryStep.PROCESS_EXTRACTION,
                lambda: self._process.run(ctx, chunks),
                input_summary={"chunk_count": len(chunks)},
                output_summary=lambda r: r.trace,
            )
        except Exception:
            had_optional_failures = True

        try:
            relationship_result = self._run_step(
                ctx,
                flow_ctx,
                DiscoveryStep.RELATIONSHIP_BUILD,
                lambda: self._relationship.run(
                    ctx,
                    build_input=RelationshipBuildInput(
                        chunks=tuple(chunks),
                        entities=tuple(entities),
                        mentions=tuple(mentions),
                        enrichments=tuple(enrichment_result.enrichments if enrichment_result else ()),
                        keywords=tuple(enrichment_result.keywords if enrichment_result else ()),
                        topics=tuple(enrichment_result.topics if enrichment_result else ()),
                        temporal_mentions=tuple(temporal_result.mentions if temporal_result else ()),
                        spatial_mentions=tuple(spatial_result.mentions if spatial_result else ()),
                        process_mentions=tuple(process_result.mentions if process_result else ()),
                    ),
                ),
                input_summary={"entity_count": len(entities)},
                output_summary=lambda r: r.trace,
            )
        except Exception:
            had_optional_failures = True

        try:
            scores = self._run_step(
                ctx,
                flow_ctx,
                DiscoveryStep.KNOWLEDGE_SCORING,
                lambda: self._scoring.run(
                    ctx,
                    chunks,
                    entities=entities,
                    enrichments=list(enrichment_result.enrichments) if enrichment_result else [],
                    keywords=list(enrichment_result.keywords) if enrichment_result else [],
                    topics=list(enrichment_result.topics) if enrichment_result else [],
                    entity_mentions=mentions,
                    temporal_mentions=list(temporal_result.mentions) if temporal_result else [],
                    spatial_mentions=list(spatial_result.mentions) if spatial_result else [],
                    process_mentions=list(process_result.mentions) if process_result else [],
                    relationship_count=(
                        relationship_result.relationship_count if relationship_result else 0
                    ),
                ),
                input_summary={"chunk_count": len(chunks)},
                output_summary=lambda r: {"score_count": len(r)},
            )
        except Exception:
            had_optional_failures = True

        try:
            status, checklist = self._run_step(
                ctx,
                flow_ctx,
                DiscoveryStep.VALIDATION,
                lambda: self._validate.run(
                    ctx,
                    chunks=chunks,
                    chunk_count=len(chunks),
                    enrichment_result=enrichment_result,
                    had_optional_failures=had_optional_failures,
                ),
                input_summary={"had_optional_failures": had_optional_failures},
                output_summary=lambda r: {"status": r[0].value, "warnings": list(r[1].warnings)},
            )
        except Exception as exc:
            return self._fail(ctx, flow_ctx, exc)

        if status == DiscoveryStatus.FAILED:
            self._job_repository.mark_failed(
                ctx.job_id,
                status=DiscoveryStatus.FAILED,
                error_code=DiscoveryErrorCode.VALIDATION_FAILED.value,
                error_message=f"missing: {', '.join(checklist.missing)}",
                retryable=False,
            )
            self._flow_recorder.record_stage_failed(
                flow_ctx,
                module=_PROCESSING_MODULE,
                stage="DISCOVERY",
                step="PIPELINE",
                duration_ms=0,
                message=f"missing: {', '.join(checklist.missing)}",
                error_code=DiscoveryErrorCode.VALIDATION_FAILED.value,
            )
            self._safe_emit(
                self._emit_failed,
                tenant_slug=ctx.tenant_slug,
                job_id=ctx.job_id,
                understanding_job_id=ctx.understanding_job_id,
                training_item_id=ctx.training_item_id,
                knowledge_base_id=ctx.knowledge_base_id,
                status=DiscoveryStatus.FAILED.value,
                error_code=DiscoveryErrorCode.VALIDATION_FAILED.value,
            )
            return DiscoveryStatus.FAILED

        self._job_repository.mark_completed(ctx.job_id, status)
        completion_event = (
            "DISCOVERY_READY_FOR_EMBEDDING"
            if status in (DiscoveryStatus.READY_FOR_EMBEDDING, DiscoveryStatus.PARTIAL)
            else "DISCOVERY_COMPLETED"
        )
        self._flow_recorder.record_stage_completed(
            flow_ctx,
            module=_PROCESSING_MODULE,
            stage="DISCOVERY",
            step="PIPELINE",
            event_type=completion_event,
            duration_ms=0,
            output_summary_json={"status": status.value, "warnings": list(checklist.warnings)},
        )
        self._safe_emit(
            self._emit_completed,
            tenant_slug=ctx.tenant_slug,
            job_id=ctx.job_id,
            understanding_job_id=ctx.understanding_job_id,
            training_item_id=ctx.training_item_id,
            knowledge_base_id=ctx.knowledge_base_id,
            status=status.value,
        )
        if status in (DiscoveryStatus.READY_FOR_EMBEDDING, DiscoveryStatus.PARTIAL):
            self._safe_emit(
                self._emit_embedding_requested,
                tenant_slug=ctx.tenant_slug,
                understanding_job_id=ctx.understanding_job_id,
                discovery_job_id=ctx.job_id,
                training_item_id=ctx.training_item_id,
                knowledge_base_id=ctx.knowledge_base_id,
                created_by=ctx.created_by,
            )
        return status

    def _run_step(self, ctx, flow_ctx, step, action, *, input_summary, output_summary):
        stage, step_name, started_event, completed_event = _STEP_FLOW[step]
        self._job_repository.set_status(ctx.job_id, _STEP_STATUS[step])
        self._flow_recorder.record_stage_started(
            flow_ctx,
            module=_PROCESSING_MODULE,
            stage=stage,
            step=step_name,
            event_type=started_event,
            input_summary_json=input_summary,
        )
        started = time.monotonic()
        try:
            result = action()
        except Exception as exc:
            duration_ms = int((time.monotonic() - started) * 1000)
            error_code = str(getattr(exc, "code", DiscoveryErrorCode.INTERNAL_ERROR.value))
            self._flow_recorder.record_stage_failed(
                flow_ctx,
                module=_PROCESSING_MODULE,
                stage=stage,
                step=step_name,
                duration_ms=duration_ms,
                message=str(exc),
                input_summary_json=input_summary,
                error_code=error_code,
            )
            if step in _OPTIONAL_STEPS:
                logger.warning(
                    "Discovery opcionális lépés hibázott (job=%s step=%s)",
                    ctx.job_id,
                    step.value,
                    exc_info=True,
                )
            raise
        duration_ms = int((time.monotonic() - started) * 1000)
        output = output_summary(result)
        self._flow_recorder.record_stage_completed(
            flow_ctx,
            module=_PROCESSING_MODULE,
            stage=stage,
            step=step_name,
            event_type=completed_event,
            duration_ms=duration_ms,
            input_summary_json=input_summary,
            output_summary_json=output,
        )
        return result

    def _fail(self, ctx: DiscoveryJobContext, flow_ctx: ProcessingFlowContext, exc: Exception) -> DiscoveryStatus:
        retryable = isinstance(exc, DiscoveryProcessingError) and exc.retryable
        status = DiscoveryStatus.RETRYABLE if retryable else DiscoveryStatus.FAILED
        error_code = str(getattr(exc, "code", DiscoveryErrorCode.INTERNAL_ERROR.value))
        self._job_repository.mark_failed(
            ctx.job_id,
            status=status,
            error_code=error_code,
            error_message=str(exc),
            retryable=retryable,
        )
        self._flow_recorder.record_stage_failed(
            flow_ctx,
            module=_PROCESSING_MODULE,
            stage="DISCOVERY",
            step="PIPELINE",
            duration_ms=0,
            message=str(exc),
            error_code=error_code,
        )
        self._safe_emit(
            self._emit_failed,
            tenant_slug=ctx.tenant_slug,
            job_id=ctx.job_id,
            understanding_job_id=ctx.understanding_job_id,
            training_item_id=ctx.training_item_id,
            knowledge_base_id=ctx.knowledge_base_id,
            status=status.value,
            error_code=error_code,
        )
        return status

    @staticmethod
    def _flow_context(ctx: DiscoveryJobContext) -> ProcessingFlowContext:
        return ProcessingFlowContext(
            tenant_slug=ctx.tenant_slug,
            knowledge_base_id=ctx.knowledge_base_id,
            training_batch_id=ctx.training_batch_id,
            training_item_id=ctx.training_item_id,
            job_id=ctx.job_id,
            created_by=ctx.created_by,
        )

    @staticmethod
    def _apply_language_results(
        chunks: list[DiscoveryChunkDto],
        language: LanguageDetectionResult,
    ) -> list[DiscoveryChunkDto]:
        by_id = {item.chunk_id: item for item in language.chunk_results}
        updated: list[DiscoveryChunkDto] = []
        for chunk in chunks:
            result = by_id.get(chunk.chunk_id)
            if result is None:
                updated.append(chunk)
                continue
            metadata = dict(chunk.metadata or {})
            metadata["language"] = dict(result.language_metadata)
            updated.append(
                replace(
                    chunk,
                    language_code=result.language_code,
                    language_confidence=result.language_confidence,
                    language_detected_by=result.language_detected_by,
                    metadata=metadata,
                )
            )
        return updated

    @staticmethod
    def _safe_emit(emit: Callable[..., None], **kwargs: Any) -> None:
        try:
            emit(**kwargs)
        except Exception:
            logger.warning("Discovery esemény kibocsátás sikertelen", exc_info=True)


__all__ = ["DiscoveryPipelineService"]
