from __future__ import annotations

from sqlalchemy import select

from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryStepResult
from apps.kb.kb_discovery.orm.DiscoveryStepRun import DiscoveryStepRun
from apps.kb.shared.ids import new_id


class DiscoveryStepRunRepository:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def add_run(self, job_id: str, result: DiscoveryStepResult) -> str:
        run = DiscoveryStepRun(
            id=new_id("disc_step"),
            job_id=job_id,
            step=result.step.value,
            status=result.status,
            input_summary=dict(result.input_summary),
            output_summary=dict(result.output_summary),
            duration_ms=result.duration_ms,
            error_code=result.error_code,
            error_message=(result.error_message or "")[:4000] or None,
        )
        with self._session_factory() as session:
            session.add(run)
            session.commit()
            return run.id


__all__ = ["DiscoveryStepRunRepository"]
