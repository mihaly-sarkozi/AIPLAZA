from __future__ import annotations

import logging
import time
from dataclasses import replace
from typing import Any, Callable

from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.dto.DiscoveryJobContext import DiscoveryJobContext
from apps.kb.kb_discovery.dto.LanguageDetectionResult import LanguageDetectionResult
from apps.kb.kb_discovery.enums.DiscoveryErrorCode import DiscoveryErrorCode
from apps.kb.kb_discovery.enums.DiscoveryStatus import DiscoveryStatus
from apps.kb.kb_discovery.enums.DiscoveryStep import DiscoveryStep
from apps.kb.kb_discovery.errors.DiscoveryProcessingError import DiscoveryProcessingError
from apps.kb.kb_discovery.events.discovery_completed_event import add_discovery_completed_event
from apps.kb.kb_discovery.events.discovery_failed_event import add_discovery_failed_event
from apps.kb.kb_discovery.events.embedding_requested_event import add_embedding_requested_event
from apps.kb.kb_discovery.repository.DiscoveryJobRepository import DiscoveryJobRepository
from apps.kb.kb_discovery.service.DiscoveryTraceService import DiscoveryTraceService

logger = logging.getLogger(__name__)

_OPTIONAL_STEPS = frozenset(
    {
        DiscoveryStep.LANGUAGE_DETECTION,
        DiscoveryStep.ENTITY_EXTRACTION,
        DiscoveryStep.LOCAL_KNOWLEDGE_ENRICHMENT,
        DiscoveryStep.RELATIONSHIP_BUILD,
        DiscoveryStep.KNOWLEDGE_SCORING,
    }
)

_STEP_STATUS = {
    DiscoveryStep.LANGUAGE_DETECTION: DiscoveryStatus.DETECTING_LANGUAGE,
    DiscoveryStep.ENTITY_EXTRACTION: DiscoveryStatus.EXTRACTING_ENTITIES,
    DiscoveryStep.LOCAL_KNOWLEDGE_ENRICHMENT: DiscoveryStatus.ENRICHING_LOCAL,
    DiscoveryStep.RELATIONSHIP_BUILD: DiscoveryStatus.BUILDING_RELATIONSHIPS,
    DiscoveryStep.KNOWLEDGE_SCORING: DiscoveryStatus.SCORING,
    DiscoveryStep.VALIDATION: DiscoveryStatus.VALIDATING,
}


class DiscoveryPipelineService:
    def __init__(
        self,
        job_repository: DiscoveryJobRepository,
        trace: DiscoveryTraceService,
        *,
        language_service,
        entity_service,
        enrichment_service,
        relationship_service,
        scoring_service,
        validate_service,
        emit_completed: Callable[..., None] = add_discovery_completed_event,
        emit_failed: Callable[..., None] = add_discovery_failed_event,
        emit_embedding_requested: Callable[..., None] = add_embedding_requested_event,
    ) -> None:
        self._job_repository = job_repository
        self._trace = trace
        self._language = language_service
        self._entity = entity_service
        self._enrichment = enrichment_service
        self._relationship = relationship_service
        self._scoring = scoring_service
        self._validate = validate_service
        self._emit_completed = emit_completed
        self._emit_failed = emit_failed
        self._emit_embedding_requested = emit_embedding_requested

    def run(self, ctx: DiscoveryJobContext, chunks) -> DiscoveryStatus:
        had_optional_failures = False
        entities, mentions = [], []
        enrichments = []
        enrichment_result = None
        relationship_count = 0
        scores = []

        try:
            language = self._run_step(
                ctx,
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
                DiscoveryStep.ENTITY_EXTRACTION,
                lambda: self._entity.run(ctx, chunks),
                input_summary={"chunk_count": len(chunks)},
                output_summary=lambda r: {"entity_count": len(r[0])},
            )
        except Exception:
            had_optional_failures = True

        try:
            enrichment_result = self._run_step(
                ctx,
                DiscoveryStep.LOCAL_KNOWLEDGE_ENRICHMENT,
                lambda: self._enrichment.run(ctx, chunks),
                input_summary={"chunk_count": len(chunks), "language_code": ctx.language_code},
                output_summary=lambda r: r.trace,
            )
            enrichments = list(enrichment_result.enrichments)
        except Exception:
            had_optional_failures = True

        try:
            relationship_count = self._run_step(
                ctx,
                DiscoveryStep.RELATIONSHIP_BUILD,
                lambda: self._relationship.run(ctx, entities=entities, enrichments=enrichments),
                input_summary={"entity_count": len(entities)},
                output_summary=lambda r: {"relationship_count": r},
            )
        except Exception:
            had_optional_failures = True

        try:
            scores = self._run_step(
                ctx,
                DiscoveryStep.KNOWLEDGE_SCORING,
                lambda: self._scoring.run(ctx, chunks, entities=entities, enrichments=enrichments),
                input_summary={"chunk_count": len(chunks)},
                output_summary=lambda r: {"score_count": len(r)},
            )
        except Exception:
            had_optional_failures = True

        try:
            status, checklist = self._run_step(
                ctx,
                DiscoveryStep.VALIDATION,
                lambda: self._validate.run(
                    ctx,
                    chunks=chunks,
                    chunk_count=len(chunks),
                    enrichment_result=enrichment_result,
                    had_optional_failures=had_optional_failures,
                ),
                input_summary={"had_optional_failures": had_optional_failures},
                output_summary=lambda r: {"status": r[0].value},
            )
        except Exception as exc:
            return self._fail(ctx, exc)

        if status == DiscoveryStatus.FAILED:
            self._job_repository.mark_failed(
                ctx.job_id,
                status=DiscoveryStatus.FAILED,
                error_code=DiscoveryErrorCode.VALIDATION_FAILED.value,
                error_message=f"missing: {', '.join(checklist.missing)}",
                retryable=False,
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

    def _run_step(self, ctx, step, action, *, input_summary, output_summary):
        self._job_repository.set_status(ctx.job_id, _STEP_STATUS[step])
        started = time.monotonic()
        try:
            result = action()
        except Exception as exc:
            duration_ms = int((time.monotonic() - started) * 1000)
            error_code = getattr(exc, "code", DiscoveryErrorCode.INTERNAL_ERROR.value)
            self._trace.record(
                ctx.job_id,
                step,
                status="failed",
                duration_ms=duration_ms,
                input_summary=input_summary,
                error_code=str(error_code),
                error_message=str(exc),
            )
            if step in _OPTIONAL_STEPS:
                logger.warning("Discovery opcionális lépés hibázott (job=%s step=%s)", ctx.job_id, step.value, exc_info=True)
            raise
        duration_ms = int((time.monotonic() - started) * 1000)
        self._trace.record(
            ctx.job_id,
            step,
            status="completed",
            duration_ms=duration_ms,
            input_summary=input_summary,
            output_summary=output_summary(result),
        )
        return result

    def _fail(self, ctx: DiscoveryJobContext, exc: Exception) -> DiscoveryStatus:
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
