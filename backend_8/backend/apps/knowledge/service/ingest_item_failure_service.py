from __future__ import annotations

from typing import Any

from apps.knowledge.domain.ingest_item import IngestItem
from apps.knowledge.domain.ingest_run import IngestRun


class IngestItemFailureService:
    def __init__(
        self,
        *,
        ingest_runs: Any,
        progress_service: Any,
        record_ingest_event: Any,
        metrics_store: Any,
        log_step: Any,
        truncate_error_message: Any,
        parser_error_message_max: int,
    ) -> None:
        self._ingest_runs = ingest_runs
        self._progress_service = progress_service
        self._record_ingest_event = record_ingest_event
        self._metrics_store = metrics_store
        self._log_step = log_step
        self._truncate_error_message = truncate_error_message
        self._parser_error_message_max = parser_error_message_max

    def mark_missing_input(self, *, run: IngestRun, item: IngestItem) -> bool:
        failed_item = self._ingest_runs().mark_item_failed(
            item,
            error_code="missing_input",
            error_message="Nem található ingest input rekord.",
            progress_message="Hiányzó input rekord.",
        )
        failed_item = self._mark_modules_failed(failed_item, failed_item.error_message)
        self._record_ingest_event(
            run_id=run.id,
            item_id=item.id,
            event_type="validation_failed",
            status="failed",
            message=failed_item.error_message,
            error_code=failed_item.error_code,
        )
        return bool(run.continue_on_error)

    def mark_processing_failed(
        self,
        *,
        run: IngestRun,
        item: IngestItem,
        exc: Exception,
        force_reprocess: bool,
    ) -> bool:
        safe_error_message = self._truncate_error_message(exc, max_length=self._parser_error_message_max)
        failed_item = self._ingest_runs().mark_item_failed(
            item,
            error_code="processing_failed",
            error_message=safe_error_message,
            progress_message="Ingest feldolgozás közben hiba történt.",
        )
        failed_item = self._mark_modules_failed(failed_item, safe_error_message)
        self._record_ingest_event(
            run_id=run.id,
            item_id=item.id,
            event_type="item_failed",
            status="failed",
            message=safe_error_message,
            force_reprocess=force_reprocess,
        )
        self._metrics_store.increment("ingest_item_failed_count", 1)
        self._log_step(
            "ingest.item.failed",
            status="error",
            tenant=run.tenant,
            ingest_run_id=run.id,
            ingest_item_id=failed_item.id,
        )
        return bool(run.continue_on_error)

    def _mark_modules_failed(self, item: IngestItem, error_message: str | None) -> IngestItem:
        return self._progress_service.update_item_processing_summary(
            item,
            module_updates={
                "parser": self._progress_service.build_processing_module(
                    key="parser",
                    status="failed",
                    label="Mondatkinyerés",
                    error_message=error_message,
                ),
                "sentence_interpretation": self._progress_service.build_processing_module(
                    key="sentence_interpretation",
                    status="failed",
                    label="Mondatértelmezés",
                    error_message=error_message,
                ),
                "sentence_evaluation": self._progress_service.build_processing_module(
                    key="sentence_evaluation",
                    status="failed",
                    label="Mondatértékelés",
                    error_message=error_message,
                ),
            },
        )


__all__ = ["IngestItemFailureService"]
