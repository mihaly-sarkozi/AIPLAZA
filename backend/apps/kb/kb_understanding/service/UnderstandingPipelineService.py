from __future__ import annotations

# backend/apps/kb/kb_understanding/service/UnderstandingPipelineService.py
# Feladat: A megértési pipeline orchestrálása — CSAK összefűz: lépések sorban,
# státuszváltás + trace lépésenként, hibaosztályozás (RETRYABLE/FAILED/PARTIAL),
# siker végén indexing_requested esemény. Üzleti logika a lépés-service-ekben van.
# Sárközi Mihály - 2026.06.11

import logging
import time
from typing import Any, Callable

from apps.kb.kb_understanding.dto.UnderstandingJobContext import UnderstandingJobContext
from apps.kb.kb_understanding.enums.UnderstandingErrorCode import UnderstandingErrorCode
from apps.kb.kb_understanding.enums.UnderstandingStatus import UnderstandingStatus
from apps.kb.kb_understanding.enums.UnderstandingStep import UnderstandingStep
from apps.kb.kb_understanding.errors.UnderstandingProcessingError import UnderstandingProcessingError
from apps.kb.kb_understanding.events.indexing_requested_event import add_indexing_requested_event
from apps.kb.kb_understanding.events.understanding_completed_event import (
    add_understanding_completed_event,
)
from apps.kb.kb_understanding.events.understanding_failed_event import (
    add_understanding_failed_event,
)
from apps.kb.kb_understanding.repository.UnderstandingJobRepository import (
    UnderstandingJobRepository,
)
from apps.kb.kb_understanding.service.ProcessingTraceService import ProcessingTraceService

logger = logging.getLogger(__name__)

# Opcionális lépések — hibájuk nem állítja le a pipeline-t, a vége PARTIAL lesz.
_OPTIONAL_STEPS = {
    UnderstandingStep.ENTITY_EXTRACTION,
    UnderstandingStep.KNOWLEDGE_ENRICHMENT,
    UnderstandingStep.RELATIONSHIP_BUILD,
    UnderstandingStep.KNOWLEDGE_SCORING,
}


class UnderstandingPipelineService:
    def __init__(
        self,
        job_repository: UnderstandingJobRepository,
        trace: ProcessingTraceService,
        *,
        extract_service,
        normalize_service,
        structure_service,
        chunk_service,
        entities_service,
        enrich_service,
        embed_service,
        relationships_service,
        score_service,
        validate_service,
        emit_completed: Callable[..., None] = add_understanding_completed_event,
        emit_failed: Callable[..., None] = add_understanding_failed_event,
        emit_indexing_requested: Callable[..., None] = add_indexing_requested_event,
    ) -> None:
        self._job_repository = job_repository
        self._trace = trace
        self._extract = extract_service
        self._normalize = normalize_service
        self._structure = structure_service
        self._chunk = chunk_service
        self._entities = entities_service
        self._enrich = enrich_service
        self._embed = embed_service
        self._relationships = relationships_service
        self._score = score_service
        self._validate = validate_service
        self._emit_completed = emit_completed
        self._emit_failed = emit_failed
        self._emit_indexing_requested = emit_indexing_requested

    def run(self, ctx: UnderstandingJobContext) -> UnderstandingStatus:
        had_optional_failures = False

        # --- Kötelező determinisztikus lépések -----------------------------
        try:
            extracted = self._run_step(
                ctx,
                UnderstandingStep.EXTRACT,
                UnderstandingStatus.EXTRACTING,
                lambda: self._extract.run(ctx),
                input_summary={"raw_ref": ctx.raw_ref, "mime_type": ctx.mime_type},
                output_summary=lambda result: {"char_count": result.char_count, "extractor": result.extractor},
            )
            normalized = self._run_step(
                ctx,
                UnderstandingStep.NORMALIZE,
                UnderstandingStatus.NORMALIZING,
                lambda: self._normalize.run(ctx, extracted),
                input_summary={"char_count": extracted.char_count},
                output_summary=lambda result: {"char_count": result.char_count, "applied_rules": result.applied_rules},
            )
            blocks = self._run_step(
                ctx,
                UnderstandingStep.STRUCTURE_DETECTION,
                UnderstandingStatus.STRUCTURING,
                lambda: self._structure.run(ctx, normalized),
                input_summary={"char_count": normalized.char_count},
                output_summary=lambda result: {"block_count": len(result)},
            )
            chunks = self._run_step(
                ctx,
                UnderstandingStep.CHUNKING,
                UnderstandingStatus.CHUNKING,
                lambda: self._chunk.run(ctx, blocks),
                input_summary={"block_count": len(blocks)},
                output_summary=lambda result: {"chunk_count": len(result)},
            )
        except Exception as exc:
            return self._fail(ctx, exc)

        # --- AI lépések (entitás / enrichment opcionális) -------------------
        entities = []
        try:
            entities = self._run_step(
                ctx,
                UnderstandingStep.ENTITY_EXTRACTION,
                UnderstandingStatus.EXTRACTING_ENTITIES,
                lambda: self._entities.run(ctx, chunks),
                input_summary={"chunk_count": len(chunks)},
                output_summary=lambda result: {"entity_count": len(result)},
            )
        except Exception:
            had_optional_failures = True

        enrichments = []
        try:
            enrichments = self._run_step(
                ctx,
                UnderstandingStep.KNOWLEDGE_ENRICHMENT,
                UnderstandingStatus.ENRICHING,
                lambda: self._enrich.run(ctx, chunks),
                input_summary={"chunk_count": len(chunks)},
                output_summary=lambda result: {"enrichment_count": len(result)},
            )
        except Exception:
            had_optional_failures = True

        try:
            self._run_step(
                ctx,
                UnderstandingStep.EMBEDDING,
                UnderstandingStatus.EMBEDDING,
                lambda: self._embed.run(ctx, chunks, enrichments),
                input_summary={"chunk_count": len(chunks)},
                output_summary=lambda result: {"embedding_count": result},
            )
        except Exception as exc:
            return self._fail(ctx, exc)

        try:
            self._run_step(
                ctx,
                UnderstandingStep.RELATIONSHIP_BUILD,
                UnderstandingStatus.BUILDING_RELATIONSHIPS,
                lambda: self._relationships.run(ctx, entities, enrichments),
                input_summary={"entity_count": len(entities)},
                output_summary=lambda result: {"relationship_count": result},
            )
        except Exception:
            had_optional_failures = True

        try:
            self._run_step(
                ctx,
                UnderstandingStep.KNOWLEDGE_SCORING,
                UnderstandingStatus.SCORING,
                lambda: self._score.run(ctx, chunks, entities, enrichments),
                input_summary={"chunk_count": len(chunks)},
                output_summary=lambda result: {"score_count": len(result)},
            )
        except Exception:
            had_optional_failures = True

        # --- Validáció és lezárás -------------------------------------------
        try:
            status, checklist = self._run_step(
                ctx,
                UnderstandingStep.VALIDATION,
                UnderstandingStatus.VALIDATING,
                lambda: self._validate.run(ctx, had_optional_failures=had_optional_failures),
                input_summary={"had_optional_failures": had_optional_failures},
                output_summary=lambda result: {"status": result[0].value, "missing": list(result[1].missing)},
            )
        except Exception as exc:
            return self._fail(ctx, exc)

        if status == UnderstandingStatus.FAILED:
            self._job_repository.mark_failed(
                ctx.job_id,
                status=UnderstandingStatus.FAILED,
                error_code=UnderstandingErrorCode.VALIDATION_FAILED.value,
                error_message=f"missing: {', '.join(checklist.missing)}",
                retryable=False,
            )
            self._safe_emit(
                self._emit_failed,
                tenant_slug=ctx.tenant_slug,
                job_id=ctx.job_id,
                training_item_id=ctx.training_item_id,
                knowledge_base_id=ctx.knowledge_base_id,
                status=UnderstandingStatus.FAILED.value,
                error_code=UnderstandingErrorCode.VALIDATION_FAILED.value,
            )
            return UnderstandingStatus.FAILED

        self._job_repository.mark_completed(ctx.job_id, status)
        self._safe_emit(
            self._emit_completed,
            tenant_slug=ctx.tenant_slug,
            job_id=ctx.job_id,
            training_item_id=ctx.training_item_id,
            knowledge_base_id=ctx.knowledge_base_id,
            status=status.value,
        )
        if status == UnderstandingStatus.READY_FOR_INDEXING:
            self._safe_emit(
                self._emit_indexing_requested,
                tenant_slug=ctx.tenant_slug,
                job_id=ctx.job_id,
                training_item_id=ctx.training_item_id,
                knowledge_base_id=ctx.knowledge_base_id,
            )
        return status

    # ------------------------------------------------------------------ utils

    def _run_step(
        self,
        ctx: UnderstandingJobContext,
        step: UnderstandingStep,
        status: UnderstandingStatus,
        action: Callable[[], Any],
        *,
        input_summary: dict[str, Any],
        output_summary: Callable[[Any], dict[str, Any]],
    ) -> Any:
        self._job_repository.set_status(ctx.job_id, status)
        started = time.monotonic()
        try:
            result = action()
        except Exception as exc:
            duration_ms = int((time.monotonic() - started) * 1000)
            error_code = getattr(exc, "code", UnderstandingErrorCode.INTERNAL_ERROR.value)
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
                logger.warning(
                    "Opcionális lépés hibázott, a pipeline folytatódik (job=%s step=%s)",
                    ctx.job_id,
                    step.value,
                    exc_info=True,
                )
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

    def _fail(self, ctx: UnderstandingJobContext, exc: Exception) -> UnderstandingStatus:
        retryable = isinstance(exc, UnderstandingProcessingError) and exc.retryable
        status = UnderstandingStatus.RETRYABLE if retryable else UnderstandingStatus.FAILED
        error_code = str(getattr(exc, "code", UnderstandingErrorCode.INTERNAL_ERROR.value))
        logger.error(
            "Megértési pipeline hiba (job=%s item=%s code=%s retryable=%s)",
            ctx.job_id,
            ctx.training_item_id,
            error_code,
            retryable,
            exc_info=True,
        )
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
            training_item_id=ctx.training_item_id,
            knowledge_base_id=ctx.knowledge_base_id,
            status=status.value,
            error_code=error_code,
        )
        return status

    @staticmethod
    def _safe_emit(emit: Callable[..., None], **kwargs: Any) -> None:
        try:
            emit(**kwargs)
        except Exception:
            logger.warning("Esemény kibocsátás sikertelen", exc_info=True)


__all__ = ["UnderstandingPipelineService"]
