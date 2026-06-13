from __future__ import annotations

from typing import Any

from apps.kb.kb_processing.enums.ProcessingEventType import ProcessingEventType
from apps.kb.kb_processing.service.ProcessingEventService import ProcessingEventService
from apps.kb.kb_processing.service.ProcessingIssueService import ProcessingIssueService
from apps.kb.kb_processing.service.ProcessingMetricsService import ProcessingMetricsService
from apps.kb.shared.ports.processing_flow_recorder import ProcessingFlowContext


class KbProcessingFlowRecorder:
    def __init__(
        self,
        event_service: ProcessingEventService,
        issue_service: ProcessingIssueService,
        metrics_service: ProcessingMetricsService,
    ) -> None:
        self._events = event_service
        self._issues = issue_service
        self._metrics = metrics_service

    def record_stage_started(
        self,
        ctx: ProcessingFlowContext,
        *,
        module: str,
        stage: str,
        step: str,
        event_type: str,
        input_summary_json: dict[str, Any] | None = None,
    ) -> None:
        self._events.record_started(
            tenant_slug=ctx.tenant_slug,
            knowledge_base_id=ctx.knowledge_base_id,
            training_batch_id=ctx.training_batch_id,
            training_item_id=ctx.training_item_id,
            job_id=ctx.job_id,
            module=module,
            stage=stage,
            step=step,
            event_type=event_type,
            input_summary_json=input_summary_json,
            created_by=ctx.created_by,
        )

    def record_stage_completed(
        self,
        ctx: ProcessingFlowContext,
        *,
        module: str,
        stage: str,
        step: str,
        event_type: str,
        duration_ms: int,
        input_summary_json: dict[str, Any] | None = None,
        output_summary_json: dict[str, Any] | None = None,
    ) -> None:
        self._events.record_completed(
            tenant_slug=ctx.tenant_slug,
            knowledge_base_id=ctx.knowledge_base_id,
            training_batch_id=ctx.training_batch_id,
            training_item_id=ctx.training_item_id,
            job_id=ctx.job_id,
            module=module,
            stage=stage,
            step=step,
            event_type=event_type,
            duration_ms=duration_ms,
            input_summary_json=input_summary_json,
            output_summary_json=output_summary_json,
            created_by=ctx.created_by,
        )

    def record_stage_failed(
        self,
        ctx: ProcessingFlowContext,
        *,
        module: str,
        stage: str,
        step: str,
        duration_ms: int,
        message: str | None = None,
        input_summary_json: dict[str, Any] | None = None,
        error_code: str | None = None,
    ) -> None:
        self._events.record_failed(
            tenant_slug=ctx.tenant_slug,
            knowledge_base_id=ctx.knowledge_base_id,
            training_batch_id=ctx.training_batch_id,
            training_item_id=ctx.training_item_id,
            job_id=ctx.job_id,
            module=module,
            stage=stage,
            step=step,
            message=message,
            duration_ms=duration_ms,
            input_summary_json=input_summary_json,
            metadata_json={"error_code": error_code} if error_code else None,
            created_by=ctx.created_by,
        )

    def open_issue(
        self,
        ctx: ProcessingFlowContext,
        *,
        module: str,
        stage: str,
        step: str | None,
        severity: str,
        issue_code: str,
        issue_message: str | None = None,
        metadata_json: dict[str, Any] | None = None,
    ) -> None:
        self._issues.open_issue(
            tenant_slug=ctx.tenant_slug,
            knowledge_base_id=ctx.knowledge_base_id,
            training_batch_id=ctx.training_batch_id,
            training_item_id=ctx.training_item_id,
            job_id=ctx.job_id,
            module=module,
            stage=stage,
            step=step,
            severity=severity,
            issue_code=issue_code,
            issue_message=issue_message,
            metadata_json=metadata_json,
        )

    def recalculate_metrics(self, ctx: ProcessingFlowContext) -> None:
        self._metrics.update_after_understanding(
            ctx.knowledge_base_id,
            tenant_slug=ctx.tenant_slug,
        )


__all__ = ["KbProcessingFlowRecorder"]
