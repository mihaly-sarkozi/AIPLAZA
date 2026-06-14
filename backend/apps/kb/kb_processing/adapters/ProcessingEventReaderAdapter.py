from __future__ import annotations

from apps.kb.kb_processing.orm.ProcessingEvent import ProcessingEvent
from apps.kb.kb_processing.repository.ProcessingEventRepository import ProcessingEventRepository
from apps.kb.shared.ports.processing_event_reader import ProcessingEventReaderPort, ProcessingStepEventView


class ProcessingEventReaderAdapter(ProcessingEventReaderPort):
    _TERMINAL_STATUSES = frozenset({"completed", "failed", "skipped"})

    def __init__(self, event_repository: ProcessingEventRepository) -> None:
        self._event_repository = event_repository

    def list_for_job(self, job_id: str, *, module: str | None = None) -> list[ProcessingStepEventView]:
        rows = self._event_repository.list_for_job(job_id, module=module)
        latest_by_step: dict[str, ProcessingEvent] = {}
        for row in rows:
            if self._normalize_status(row.status) in self._TERMINAL_STATUSES:
                latest_by_step[row.step] = row
        ordered = sorted(latest_by_step.values(), key=lambda item: (item.created_at, item.id))
        return [self._to_view(row) for row in ordered]

    @staticmethod
    def _normalize_status(status: str | None) -> str:
        return str(status or "").strip().lower()

    @staticmethod
    def _to_view(row: ProcessingEvent) -> ProcessingStepEventView:
        metadata = dict(row.metadata_json or {})
        return ProcessingStepEventView(
            step=row.step,
            stage=row.stage,
            status=ProcessingEventReaderAdapter._normalize_status(row.status),
            event_type=row.event_type,
            duration_ms=row.duration_ms,
            input_summary=dict(row.input_summary_json or {}),
            output_summary=dict(row.output_summary_json or {}),
            error_code=metadata.get("error_code"),
            error_message=row.message,
            created_at=row.created_at,
        )


__all__ = ["ProcessingEventReaderAdapter"]
