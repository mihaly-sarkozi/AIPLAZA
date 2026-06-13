from __future__ import annotations

import logging
from typing import Any

from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryStepResult
from apps.kb.kb_discovery.enums.DiscoveryStep import DiscoveryStep
from apps.kb.kb_discovery.repository.DiscoveryStepRunRepository import DiscoveryStepRunRepository


logger = logging.getLogger(__name__)


class DiscoveryTraceService:
    def __init__(self, step_run_repository: DiscoveryStepRunRepository) -> None:
        self._step_run_repository = step_run_repository

    def record(
        self,
        job_id: str,
        step: DiscoveryStep,
        *,
        status: str,
        duration_ms: int,
        input_summary: dict[str, Any] | None = None,
        output_summary: dict[str, Any] | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> DiscoveryStepResult:
        result = DiscoveryStepResult(
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
            logger.warning("Discovery trace írás sikertelen (job=%s step=%s)", job_id, step.value, exc_info=True)
        return result


__all__ = ["DiscoveryTraceService"]
