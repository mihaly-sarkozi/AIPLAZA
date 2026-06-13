from __future__ import annotations

import logging
import time
from typing import Any, Callable

from apps.kb.kb_understanding.dto.UnderstandingJobContext import UnderstandingJobContext
from apps.kb.kb_understanding.enums.UnderstandingErrorCode import UnderstandingErrorCode
from apps.kb.kb_understanding.enums.UnderstandingStatus import UnderstandingStatus
from apps.kb.kb_understanding.enums.UnderstandingStep import UnderstandingStep
from apps.kb.kb_understanding.errors.UnderstandingProcessingError import UnderstandingProcessingError
from apps.kb.kb_understanding.events.discovery_requested_event import (
    enqueue_discovery_requested,
)
from apps.kb.kb_understanding.events.understanding_failed_event import (
    add_understanding_failed_event,
)
from apps.kb.kb_understanding.repository.UnderstandingJobRepository import (
    UnderstandingJobRepository,
)
from apps.kb.kb_understanding.service.ProcessingTraceService import ProcessingTraceService

logger = logging.getLogger(__name__)


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
        validate_service,
        emit_discovery_requested: Callable[..., None] = enqueue_discovery_requested,
        emit_failed: Callable[..., None] = add_understanding_failed_event,
    ) -> None:
        self._job_repository = job_repository
        self._trace = trace
        self._extract = extract_service
        self._normalize = normalize_service
        self._structure = structure_service
        self._chunk = chunk_service
        self._validate = validate_service
        self._emit_discovery_requested = emit_discovery_requested
        self._emit_failed = emit_failed

    def run(self, ctx: UnderstandingJobContext) -> UnderstandingStatus:
        try:
            extracted = self._run_step(
                ctx,
                UnderstandingStep.EXTRACT,
                UnderstandingStatus.EXTRACTING,
                lambda: self._extract.run(ctx),
                input_summary={"raw_ref": ctx.raw_ref, "mime_type": ctx.mime_type},
                output_summary=lambda result: dict(result.trace_summary),
            )
            normalized = self._run_step(
                ctx,
                UnderstandingStep.NORMALIZE,
                UnderstandingStatus.NORMALIZING,
                lambda: self._normalize.run(ctx, extracted),
                input_summary={"char_count": extracted.char_count},
                output_summary=lambda result: dict(result.trace_summary),
            )
            blocks = self._run_step(
                ctx,
                UnderstandingStep.STRUCTURE_DETECTION,
                UnderstandingStatus.STRUCTURING,
                lambda: self._structure.run(ctx, normalized),
                input_summary={"char_count": normalized.char_count},
                output_summary=lambda result: {"block_count": len(result)},
            )
            self._run_step(
                ctx,
                UnderstandingStep.CHUNKING,
                UnderstandingStatus.CHUNKING,
                lambda: self._chunk.run(ctx, blocks),
                input_summary={"block_count": len(blocks)},
                output_summary=lambda result: {"chunk_count": len(result)},
            )
        except Exception as exc:
            return self._fail(ctx, exc)

        try:
            status, checklist = self._run_step(
                ctx,
                UnderstandingStep.VALIDATION,
                UnderstandingStatus.VALIDATING,
                lambda: self._validate.run(ctx),
                input_summary={},
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
                training_batch_id=ctx.training_batch_id,
                created_by=ctx.created_by,
                status=UnderstandingStatus.FAILED.value,
                error_code=UnderstandingErrorCode.VALIDATION_FAILED.value,
            )
            return UnderstandingStatus.FAILED

        self._job_repository.mark_completed(ctx.job_id, status)
        self._safe_emit(
            self._emit_discovery_requested,
            tenant_slug=ctx.tenant_slug,
            knowledge_base_id=ctx.knowledge_base_id,
            training_batch_id=ctx.training_batch_id,
            training_item_id=ctx.training_item_id,
            understanding_job_id=ctx.job_id,
            created_by=ctx.created_by,
        )
        return status

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
            training_batch_id=ctx.training_batch_id,
            created_by=ctx.created_by,
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
