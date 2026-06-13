from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class ProcessingFlowContext:
    tenant_slug: str | None
    knowledge_base_id: str
    training_batch_id: str | None
    training_item_id: str | None
    job_id: str | None
    created_by: int | None = None


class ProcessingFlowRecorder(Protocol):
    def record_stage_started(
        self,
        ctx: ProcessingFlowContext,
        *,
        module: str,
        stage: str,
        step: str,
        event_type: str,
        input_summary_json: dict[str, Any] | None = None,
    ) -> None: ...

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
    ) -> None: ...

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
    ) -> None: ...

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
    ) -> None: ...

    def recalculate_metrics(self, ctx: ProcessingFlowContext) -> None: ...


class NoOpProcessingFlowRecorder:
    def record_stage_started(self, ctx, **kwargs) -> None:
        return None

    def record_stage_completed(self, ctx, **kwargs) -> None:
        return None

    def record_stage_failed(self, ctx, **kwargs) -> None:
        return None

    def open_issue(self, ctx, **kwargs) -> None:
        return None

    def recalculate_metrics(self, ctx) -> None:
        return None


__all__ = ["NoOpProcessingFlowRecorder", "ProcessingFlowContext", "ProcessingFlowRecorder"]
