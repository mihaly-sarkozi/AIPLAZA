from __future__ import annotations

# backend/apps/kb/kb_understanding/service/ProcessingTraceService.py
# Feladat: Pipeline-lépés futások naplózása (input/output összegzés, futásidő, hiba).
# Sárközi Mihály - 2026.06.11

import logging
from typing import Any

from apps.kb.kb_understanding.dto.UnderstandingStepResult import UnderstandingStepResult
from apps.kb.kb_understanding.enums.UnderstandingStep import UnderstandingStep
from apps.kb.kb_understanding.repository.UnderstandingStepRunRepository import (
    UnderstandingStepRunRepository,
)

logger = logging.getLogger(__name__)


class ProcessingTraceService:
    def __init__(self, step_run_repository: UnderstandingStepRunRepository) -> None:
        self._step_run_repository = step_run_repository

    def record(
        self,
        job_id: str,
        step: UnderstandingStep,
        *,
        status: str,
        duration_ms: int,
        input_summary: dict[str, Any] | None = None,
        output_summary: dict[str, Any] | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> UnderstandingStepResult:
        result = UnderstandingStepResult(
            step=step,
            status=status,
            duration_ms=duration_ms,
            input_summary=dict(input_summary or {}),
            output_summary=dict(output_summary or {}),
            error_code=error_code,
            error_message=error_message,
        )
        try:
            self._step_run_repository.add_run(job_id, result)
        except Exception:
            # A trace-írás hibája nem buktathatja a pipeline-t.
            logger.warning("Trace írás sikertelen (job=%s step=%s)", job_id, step.value, exc_info=True)
        return result


__all__ = ["ProcessingTraceService"]
