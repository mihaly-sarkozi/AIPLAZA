from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol


@dataclass(frozen=True)
class ProcessingStepEventView:
    step: str
    stage: str
    status: str
    event_type: str
    duration_ms: int | None
    input_summary: dict[str, Any]
    output_summary: dict[str, Any]
    error_code: str | None
    error_message: str | None
    created_at: datetime | None


class ProcessingEventReaderPort(Protocol):
    def list_for_job(self, job_id: str, *, module: str | None = None) -> list[ProcessingStepEventView]: ...


class NoOpProcessingEventReader:
    def list_for_job(self, job_id: str, *, module: str | None = None) -> list[ProcessingStepEventView]:
        return []


__all__ = ["NoOpProcessingEventReader", "ProcessingEventReaderPort", "ProcessingStepEventView"]
