from __future__ import annotations

import logging
from typing import Any

from apps.kb.kb_processing.enums.ProcessingEventStatus import ProcessingEventStatus
from apps.kb.kb_processing.enums.ProcessingEventType import ProcessingEventType
from apps.kb.kb_processing.repository.ProcessingEventRepository import ProcessingEventRepository

logger = logging.getLogger(__name__)


class ProcessingEventService:
    def __init__(self, event_repository: ProcessingEventRepository) -> None:
        self._event_repository = event_repository

    def record_started(
        self,
        *,
        tenant_slug: str | None,
        knowledge_base_id: str,
        training_batch_id: str | None,
        training_item_id: str | None,
        job_id: str | None,
        module: str,
        stage: str,
        step: str,
        event_type: ProcessingEventType | str,
        message: str | None = None,
        input_summary_json: dict[str, Any] | None = None,
        metadata_json: dict[str, Any] | None = None,
        created_by: int | None = None,
    ) -> None:
        self._safe_record(
            tenant_slug=tenant_slug,
            knowledge_base_id=knowledge_base_id,
            training_batch_id=training_batch_id,
            training_item_id=training_item_id,
            job_id=job_id,
            module=module,
            stage=stage,
            step=step,
            event_type=str(event_type),
            status=ProcessingEventStatus.STARTED.value,
            message=message,
            input_summary_json=input_summary_json,
            metadata_json=metadata_json,
            created_by=created_by,
        )

    def record_completed(
        self,
        *,
        tenant_slug: str | None,
        knowledge_base_id: str,
        training_batch_id: str | None,
        training_item_id: str | None,
        job_id: str | None,
        module: str,
        stage: str,
        step: str,
        event_type: ProcessingEventType | str,
        duration_ms: int | None = None,
        message: str | None = None,
        input_summary_json: dict[str, Any] | None = None,
        output_summary_json: dict[str, Any] | None = None,
        metadata_json: dict[str, Any] | None = None,
        created_by: int | None = None,
    ) -> None:
        self._safe_record(
            tenant_slug=tenant_slug,
            knowledge_base_id=knowledge_base_id,
            training_batch_id=training_batch_id,
            training_item_id=training_item_id,
            job_id=job_id,
            module=module,
            stage=stage,
            step=step,
            event_type=str(event_type),
            status=ProcessingEventStatus.COMPLETED.value,
            message=message,
            duration_ms=duration_ms,
            input_summary_json=input_summary_json,
            output_summary_json=output_summary_json,
            metadata_json=metadata_json,
            created_by=created_by,
        )

    def record_failed(
        self,
        *,
        tenant_slug: str | None,
        knowledge_base_id: str,
        training_batch_id: str | None,
        training_item_id: str | None,
        job_id: str | None,
        module: str,
        stage: str,
        step: str,
        message: str | None = None,
        duration_ms: int | None = None,
        input_summary_json: dict[str, Any] | None = None,
        output_summary_json: dict[str, Any] | None = None,
        metadata_json: dict[str, Any] | None = None,
        created_by: int | None = None,
    ) -> None:
        self._safe_record(
            tenant_slug=tenant_slug,
            knowledge_base_id=knowledge_base_id,
            training_batch_id=training_batch_id,
            training_item_id=training_item_id,
            job_id=job_id,
            module=module,
            stage=stage,
            step=step,
            event_type=ProcessingEventType.STEP_FAILED.value,
            status=ProcessingEventStatus.FAILED.value,
            message=message,
            duration_ms=duration_ms,
            input_summary_json=input_summary_json,
            output_summary_json=output_summary_json,
            metadata_json=metadata_json,
            created_by=created_by,
        )

    def record_skipped(
        self,
        *,
        tenant_slug: str | None,
        knowledge_base_id: str,
        training_batch_id: str | None,
        training_item_id: str | None,
        job_id: str | None,
        module: str,
        stage: str,
        step: str,
        message: str | None = None,
        input_summary_json: dict[str, Any] | None = None,
        metadata_json: dict[str, Any] | None = None,
        created_by: int | None = None,
    ) -> None:
        self._safe_record(
            tenant_slug=tenant_slug,
            knowledge_base_id=knowledge_base_id,
            training_batch_id=training_batch_id,
            training_item_id=training_item_id,
            job_id=job_id,
            module=module,
            stage=stage,
            step=step,
            event_type=ProcessingEventType.STEP_SKIPPED.value,
            status=ProcessingEventStatus.SKIPPED.value,
            message=message,
            input_summary_json=input_summary_json,
            metadata_json=metadata_json,
            created_by=created_by,
        )

    def _safe_record(self, **kwargs: Any) -> None:
        try:
            self._event_repository.add_event(**kwargs)
        except Exception:
            logger.warning(
                "Processing event írás sikertelen (kb=%s step=%s)",
                kwargs.get("knowledge_base_id"),
                kwargs.get("step"),
                exc_info=True,
            )


__all__ = ["ProcessingEventService"]
