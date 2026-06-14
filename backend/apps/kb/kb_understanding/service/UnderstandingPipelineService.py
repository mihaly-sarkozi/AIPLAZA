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
from apps.kb.shared.ports.processing_flow_recorder import (
    NoOpProcessingFlowRecorder,
    ProcessingFlowContext,
    ProcessingFlowRecorder,
)

logger = logging.getLogger(__name__)

_PROCESSING_MODULE = "kb_understanding"

_STEP_FLOW = {
    UnderstandingStep.EXTRACT: (
        "EXTRACT",
        "EXTRACT_CONTENT",
        "EXTRACT_STARTED",
        "EXTRACT_COMPLETED",
    ),
    UnderstandingStep.NORMALIZE: (
        "NORMALIZE",
        "NORMALIZE_PARTS",
        "NORMALIZE_STARTED",
        "NORMALIZE_COMPLETED",
    ),
    UnderstandingStep.CHUNKING: (
        "CHUNKING",
        "BUILD_CHUNKS",
        "CHUNKING_STARTED",
        "CHUNKING_COMPLETED",
    ),
    UnderstandingStep.VALIDATION: (
        "VALIDATION",
        "VALIDATE_RESULT",
        "VALIDATION_STARTED",
        "VALIDATION_COMPLETED",
    ),
}

_ERROR_ISSUE_MAP: dict[str, tuple[str, str]] = {
    UnderstandingErrorCode.OCR_FAILED.value: ("WARNING", "OCR_FAILED"),
    UnderstandingErrorCode.EMPTY_CONTENT.value: ("ERROR", "NO_USABLE_PARTS"),
    UnderstandingErrorCode.EXTRACTION_FAILED.value: ("ERROR", "EXTRACTION_FAILED"),
    UnderstandingErrorCode.DOCX_PART_PARSE_ERROR.value: ("ERROR", "DOCX_PARSE_FAILED"),
    UnderstandingErrorCode.NORMALIZATION_FAILED.value: ("ERROR", "NORMALIZE_PART_FAILED"),
    UnderstandingErrorCode.NO_CHUNKS.value: ("ERROR", "NO_CHUNKS_CREATED"),
    UnderstandingErrorCode.CHUNKING_FAILED.value: ("ERROR", "NO_CHUNKS_CREATED"),
    UnderstandingErrorCode.VALIDATION_FAILED.value: ("ERROR", "VALIDATION_FAILED"),
}

_CHECKLIST_ISSUE_MAP: dict[str, tuple[str, str]] = {
    "usable_parts": ("ERROR", "NO_USABLE_PARTS"),
    "normalized_parts": ("WARNING", "LOW_NORMALIZED_PART_COUNT"),
    "chunks": ("ERROR", "NO_CHUNKS_CREATED"),
    "source_link": ("WARNING", "CHUNK_VALIDATION_WARNING"),
}


class UnderstandingPipelineService:
    def __init__(
        self,
        job_repository: UnderstandingJobRepository,
        *,
        extract_service,
        normalize_service,
        chunk_service,
        validate_service,
        flow_recorder: ProcessingFlowRecorder | None = None,
        emit_discovery_requested: Callable[..., None] = enqueue_discovery_requested,
        emit_failed: Callable[..., None] = add_understanding_failed_event,
    ) -> None:
        self._job_repository = job_repository
        self._extract = extract_service
        self._normalize = normalize_service
        self._chunk = chunk_service
        self._validate = validate_service
        self._flow_recorder = flow_recorder or NoOpProcessingFlowRecorder()
        self._emit_discovery_requested = emit_discovery_requested
        self._emit_failed = emit_failed

    def run(self, ctx: UnderstandingJobContext) -> UnderstandingStatus:
        flow_ctx = self._flow_context(ctx)
        try:
            extracted = self._run_step(
                ctx,
                flow_ctx,
                UnderstandingStep.EXTRACT,
                UnderstandingStatus.EXTRACTING,
                lambda: self._extract.run(ctx),
                input_summary={"raw_ref": ctx.raw_ref, "mime_type": ctx.mime_type},
                output_summary=lambda result: dict(result.trace_summary),
            )
            normalized = self._run_step(
                ctx,
                flow_ctx,
                UnderstandingStep.NORMALIZE,
                UnderstandingStatus.NORMALIZING,
                lambda: self._normalize.run(ctx, extracted),
                input_summary={"char_count": extracted.char_count},
                output_summary=lambda result: dict(result.trace_summary),
            )
            chunk_result = self._run_step(
                ctx,
                flow_ctx,
                UnderstandingStep.CHUNKING,
                UnderstandingStatus.CHUNKING,
                lambda: self._chunk.run(ctx, normalized),
                input_summary={"part_count": normalized.part_count},
                output_summary=lambda result: dict(result.trace_summary),
            )
        except Exception as exc:
            self._flow_recorder.recalculate_metrics(flow_ctx)
            return self._fail(ctx, flow_ctx, exc)

        try:
            status, checklist = self._run_step(
                ctx,
                flow_ctx,
                UnderstandingStep.VALIDATION,
                UnderstandingStatus.VALIDATING,
                lambda: self._validate.run(ctx),
                input_summary={"chunk_count": len(chunk_result.chunks)},
                output_summary=lambda result: {"status": result[0].value, "missing": list(result[1].missing)},
            )
        except Exception as exc:
            self._flow_recorder.recalculate_metrics(flow_ctx)
            return self._fail(ctx, flow_ctx, exc)

        if status == UnderstandingStatus.PARTIAL:
            self._flow_recorder.open_issue(
                flow_ctx,
                module=_PROCESSING_MODULE,
                stage="VALIDATION",
                step="VALIDATE_RESULT",
                severity="WARNING",
                issue_code="CHUNK_VALIDATION_WARNING",
                issue_message=f"missing: {', '.join(checklist.missing)}",
                metadata_json={"missing": list(checklist.missing)},
            )
        elif status == UnderstandingStatus.FAILED:
            self._record_checklist_issues(flow_ctx, checklist.missing)

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
            self._flow_recorder.recalculate_metrics(flow_ctx)
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
        self._flow_recorder.recalculate_metrics(flow_ctx)
        return status

    def _run_step(
        self,
        ctx: UnderstandingJobContext,
        flow_ctx: ProcessingFlowContext,
        step: UnderstandingStep,
        status: UnderstandingStatus,
        action: Callable[[], Any],
        *,
        input_summary: dict[str, Any],
        output_summary: Callable[[Any], dict[str, Any]],
    ) -> Any:
        stage, step_name, started_event, completed_event = _STEP_FLOW[step]
        self._job_repository.set_status(ctx.job_id, status)
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
            error_code = str(getattr(exc, "code", UnderstandingErrorCode.INTERNAL_ERROR.value))
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
            self._record_error_issue(flow_ctx, stage, step_name, error_code, str(exc))
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

    def _fail(
        self,
        ctx: UnderstandingJobContext,
        flow_ctx: ProcessingFlowContext,
        exc: Exception,
    ) -> UnderstandingStatus:
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

    def _record_error_issue(
        self,
        flow_ctx: ProcessingFlowContext,
        stage: str,
        step: str,
        error_code: str,
        message: str,
    ) -> None:
        mapping = _ERROR_ISSUE_MAP.get(error_code)
        if mapping is None:
            return
        severity, issue_code = mapping
        self._flow_recorder.open_issue(
            flow_ctx,
            module=_PROCESSING_MODULE,
            stage=stage,
            step=step,
            severity=severity,
            issue_code=issue_code,
            issue_message=message,
            metadata_json={"error_code": error_code},
        )

    def _record_checklist_issues(self, flow_ctx: ProcessingFlowContext, missing: tuple[str, ...]) -> None:
        for item in missing:
            mapping = _CHECKLIST_ISSUE_MAP.get(item)
            if mapping is None:
                continue
            severity, issue_code = mapping
            self._flow_recorder.open_issue(
                flow_ctx,
                module=_PROCESSING_MODULE,
                stage="VALIDATION",
                step="VALIDATE_RESULT",
                severity=severity,
                issue_code=issue_code,
                issue_message=f"validation missing: {item}",
                metadata_json={"missing_item": item},
            )

    @staticmethod
    def _flow_context(ctx: UnderstandingJobContext) -> ProcessingFlowContext:
        return ProcessingFlowContext(
            tenant_slug=ctx.tenant_slug,
            knowledge_base_id=ctx.knowledge_base_id,
            training_batch_id=ctx.training_batch_id,
            training_item_id=ctx.training_item_id,
            job_id=ctx.job_id,
            created_by=ctx.created_by,
        )

    @staticmethod
    def _safe_emit(emit: Callable[..., None], **kwargs: Any) -> None:
        try:
            emit(**kwargs)
        except Exception:
            logger.warning("Esemény kibocsátás sikertelen", exc_info=True)


__all__ = ["UnderstandingPipelineService"]
